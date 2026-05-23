from json import JSONDecodeError
from typing import Any, Dict, List, Optional, Union

from infrastructure.logging.logger import logger
from repositories.session_repository import session_repository
from schemas.session_memory import SessionMemoryState
from services.context_compression_service import context_compression_service


class SessionService:
    DEFAULT_SESSION_ID = "default_session"

    def __init__(self):
        self._repo = session_repository

    async def load_runtime_state(
        self,
        user_id: str,
        session_id: str,
        pending_user_input: str = "",
    ) -> SessionMemoryState:
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        state = self.load_session_state(user_id, target_session_id)
        runtime_state, triggered, should_persist = await context_compression_service.compress_state_if_needed(
            state,
            pending_user_input=pending_user_input,
        )

        if triggered:
            logger.info(
                "[SessionService] compression triggered user=%s session=%s should_persist=%s",
                user_id,
                target_session_id,
                should_persist,
            )

        if should_persist:
            self.save_session_state(user_id, target_session_id, runtime_state)
            if runtime_state.summary is not None:
                from services.memory_service import memory_service

                memory_service.capture_summary_memory(
                    user_id=user_id,
                    session_id=target_session_id,
                    summary=runtime_state.summary,
                )

        return runtime_state

    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        append_user_message: bool = True,
        base_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        # 中文注释：这个方法保留旧签名是为了兼容现有调用方与测试，
        # 真正的运行时上下文现在优先通过结构化会话状态来构建，不再按固定 3 轮硬截断。
        if base_history is not None:
            chat_history = list(base_history)
        else:
            state = self.load_session_state(user_id, session_id)
            chat_history = self.build_runtime_history(state)

        if append_user_message:
            chat_history.append({"role": "user", "content": user_input})
        return chat_history

    def load_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        state = self.load_session_state(user_id, session_id)
        return self.build_runtime_history(state)

    def load_session_state(self, user_id: str, session_id: str) -> SessionMemoryState:
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            session_payload = self._repo.load_session(user_id, target_session_id)
            return self._normalize_session_payload(session_payload, target_session_id)
        except JSONDecodeError as exc:
            logger.error("load session failed: user=%s session=%s error=%s", user_id, session_id, exc)
            return SessionMemoryState(
                system_messages=[
                    {
                        "role": "system",
                        "content": "会话历史已损坏，本轮仅基于当前可用信息继续处理。",
                    }
                ]
            )

    def save_session_state(self, user_id: str, session_id: str, state: SessionMemoryState):
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            self._repo.save_session(user_id, target_session_id, state.model_dump())
        except Exception as exc:
            logger.error("save session failed: user=%s session=%s error=%s", user_id, session_id, exc)

    @staticmethod
    def _sanitize_runtime_message(message: Dict[str, Any]) -> Dict[str, str]:
        return {
            "role": str(message.get("role") or "user"),
            "content": str(message.get("content") or ""),
        }

    def append_message_to_state(
        self,
        state: SessionMemoryState,
        role: str,
        content: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> SessionMemoryState:
        new_state = state.model_copy(deep=True)
        message = {"role": role, "content": content}
        if extra_fields:
            message.update(extra_fields)
        new_state.messages.append(message)
        return new_state

    def append_and_save_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> SessionMemoryState:
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        state = self.load_session_state(user_id, target_session_id)
        state = self.append_message_to_state(state, role, content, extra_fields=extra_fields)
        self.save_session_state(user_id, target_session_id, state)
        return state

    def attach_extra_fields_to_last_message(
        self,
        state: SessionMemoryState,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> SessionMemoryState:
        if not extra_fields:
            return state
        new_state = state.model_copy(deep=True)
        if not new_state.messages:
            return new_state
        new_state.messages[-1].update(extra_fields)
        return new_state

    def build_runtime_history(
        self,
        state: SessionMemoryState,
        user_input: Optional[str] = None,
        append_user_message: bool = True,
    ) -> List[Dict[str, str]]:
        runtime_history = [self._sanitize_runtime_message(message) for message in state.system_messages]
        if state.summary is not None:
            runtime_history.append(context_compression_service.format_summary_message(state.summary))
        runtime_history.extend(self._sanitize_runtime_message(message) for message in state.messages)
        if append_user_message and user_input:
            runtime_history.append({"role": "user", "content": user_input})
        return runtime_history

    def save_history(self, user_id: str, session_id: str, chat_history: List[Dict[str, Any]]):
        # 中文注释：这个兼容方法只在仍有旧调用方时兜底使用，
        # 它会把传入的消息列表重新归一成新的会话状态对象再保存。
        if chat_history is None:
            return
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            normalized_state = self._normalize_session_payload(chat_history, target_session_id)
            self.save_session_state(user_id, target_session_id, normalized_state)
        except Exception as exc:
            logger.error("save session failed: user=%s session=%s error=%s", user_id, session_id, exc)

    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        from services.hitl_service import hitl_service
        from services.task_memory_service import task_memory_service

        raw_sessions = self._repo.get_all_sessions_metadata(user_id)
        formatted_sessions = []

        for session_id, create_time, data_or_error in raw_sessions:
            session_item = {"session_id": session_id, "create_time": create_time}
            if isinstance(data_or_error, Exception):
                logger.error("load session metadata failed: %s %s", session_id, data_or_error)
                session_item.update({
                    "memory": [],
                    "total_messages": 0,
                    "error": "会话记录读取失败",
                })
            else:
                state = self._normalize_session_payload(data_or_error, session_id)
                user_visible_memory = [msg for msg in state.messages if msg.get("role") != "system"]
                pending_approval = self._build_pending_approval_payload(
                    user_id=user_id,
                    session_id=session_id,
                    task_memory_service=task_memory_service,
                    hitl_service=hitl_service,
                )
                session_item.update({
                    "memory": user_visible_memory,
                    "total_messages": len(user_visible_memory),
                    "summary": state.summary.model_dump() if state.summary else None,
                    "pending_approval": pending_approval,
                })
            formatted_sessions.append(session_item)

        formatted_sessions.sort(key=lambda item: item.get("create_time") or "", reverse=True)
        return formatted_sessions

    def _normalize_session_payload(
        self,
        payload: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]],
        session_id: str,
    ) -> SessionMemoryState:
        if payload is None:
            return SessionMemoryState(system_messages=self._init_system_msg_instruct(session_id))

        if isinstance(payload, list):
            system_messages = [msg for msg in payload if msg.get("role") == "system"]
            normal_messages = [msg for msg in payload if msg.get("role") != "system"]
            return SessionMemoryState(
                system_messages=system_messages or self._init_system_msg_instruct(session_id),
                messages=normal_messages,
            )

        if isinstance(payload, dict):
            raw_system_messages = payload.get("system_messages")
            raw_messages = payload.get("messages")
            raw_summary = payload.get("summary")
            if raw_system_messages is not None or raw_messages is not None or raw_summary is not None:
                return SessionMemoryState.model_validate(
                    {
                        "system_messages": raw_system_messages or self._init_system_msg_instruct(session_id),
                        "messages": raw_messages or [],
                        "summary": raw_summary,
                        "summary_version": payload.get("summary_version", 1),
                    }
                )

        # 中文注释：如果文件里是未知格式，就回退成初始化状态，避免因为脏数据阻断对话链路。
        logger.warning("[SessionService] unknown session payload format session=%s payload=%s", session_id, type(payload))
        return SessionMemoryState(system_messages=self._init_system_msg_instruct(session_id))

    def _build_pending_approval_payload(
        self,
        user_id: str,
        session_id: str,
        task_memory_service,
        hitl_service,
    ) -> Optional[Dict[str, Any]]:
        active_task = task_memory_service.get_active_task(user_id=user_id, session_id=session_id or "")
        if not active_task or active_task.get("task_status") != "waiting_approval":
            return None

        approval_token = active_task.get("waiting_approval_token")
        pending = hitl_service.get_pending_approval(approval_token)
        if pending is not None:
            return {
                "token": pending.token,
                "title": pending.title,
                "question": pending.question,
                "details": pending.details,
                "approveLabel": pending.approve_label,
                "rejectLabel": pending.reject_label,
            }

        approval_details = ((active_task.get("last_tool_result_json") or {}).get("approval_details")) or ""
        return {
            "token": approval_token,
            "title": "需要人工确认",
            "question": "是否允许智能体继续执行当前操作？",
            "details": approval_details,
            "approveLabel": "确认",
            "rejectLabel": "取消",
        }

    def _init_system_msg_instruct(self, session_id: str) -> List[Dict[str, str]]:
        return [{
            "role": "system",
            "content": f"你是一个多智能体助手，请基于当前会话上下文回答用户问题。(session_id={session_id})",
        }]


session_service = SessionService()
