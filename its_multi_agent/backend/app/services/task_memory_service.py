from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from infrastructure.logging.logger import logger
from repositories.task_memory_repository import task_memory_repository


class TaskMemoryService:
    CONTINUATION_PATTERNS = [
        r"继续",
        r"接着",
        r"那就",
        r"那你再",
        r"换个办法",
        r"重新查",
        r"再试试",
    ]

    APPROVAL_CONTINUATION_PATTERNS = [
        r"我同意",
        r"同意",
        r"允许",
        r"确认",
        r"继续执行",
    ]

    SERVICE_STATION_PATTERNS = [
        r"维修站",
        r"服务站",
        r"导航",
        r"修电脑",
    ]

    TECHNICAL_PATTERNS = [
        r"蓝屏",
        r"死机",
        r"黑屏",
        r"电脑",
    ]

    def __init__(self, repository=task_memory_repository) -> None:
        self._repo = repository

    def infer_task_type(self, query: str) -> Optional[str]:
        text = (query or "").strip()
        if not text:
            return None
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.SERVICE_STATION_PATTERNS):
            return "service_station_lookup"
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.TECHNICAL_PATTERNS):
            return "technical_consult"
        return None

    def should_resume_task(self, task: Optional[Dict[str, Any]], user_input: str) -> bool:
        if not task:
            return False
        text = (user_input or "").strip()
        if not text:
            return False
        if task.get("task_status") == "waiting_approval":
            return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.APPROVAL_CONTINUATION_PATTERNS)
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.CONTINUATION_PATTERNS):
            return True
        inferred = self.infer_task_type(text)
        return inferred is not None and inferred == task.get("task_type")

    def get_active_task_for_query(self, user_id: str, session_id: str, user_input: str) -> Optional[Dict[str, Any]]:
        task = self._repo.get_active_task(user_id=user_id, session_id=session_id or "")
        if self.should_resume_task(task, user_input):
            return task
        return None

    def get_active_task(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_active_task(user_id=user_id, session_id=session_id or "")

    def ensure_task(
        self,
        user_id: str,
        session_id: str,
        query: str,
        task_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        inferred = task_type or self.infer_task_type(query)
        if inferred is None:
            return None

        active_task = self._repo.get_active_task(user_id=user_id, session_id=session_id or "")
        if active_task and active_task.get("task_type") == inferred:
            return active_task
        if active_task and active_task.get("task_type") != inferred:
            self.mark_cancelled(
                user_id=user_id,
                task_id=active_task["task_id"],
                reason=f"switched_to_new_task:{inferred}",
            )

        return self._repo.create_task(
            user_id=user_id,
            session_id=session_id or "",
            task_type=inferred,
            task_goal=query,
            task_status="active",
            task_stage="intent_routed",
            task_summary=query,
            structured_context={
                "latest_user_input": query,
                "resume_hint": "继续当前任务，而不是重新开始新的任务。",
            },
        )

    def build_resume_system_messages(self, task: Dict[str, Any]) -> List[Dict[str, str]]:
        if not task:
            return []
        parts = [
            "【任务状态记忆】",
            f"任务类型：{task.get('task_type', '')}",
            f"任务目标：{task.get('task_goal', '')}",
            f"任务状态：{task.get('task_status', '')}",
            f"当前阶段：{task.get('task_stage', '')}",
        ]
        if task.get("last_tool_name"):
            parts.append(f"最近工具：{task['last_tool_name']}")
        last_tool_result = task.get("last_tool_result_json")
        if last_tool_result:
            parts.append(f"最近工具结果：{last_tool_result}")
        if task.get("last_error"):
            parts.append(f"最近错误：{task['last_error']}")
        if task.get("waiting_approval_token"):
            parts.append("当前任务正在等待人工审批，若用户同意，应恢复原任务继续执行。")
        parts.append("优先在当前任务基础上恢复执行，不要把它当作一条全新的问题。")
        return [{"role": "system", "content": "\n".join(parts)}]

    def record_task_stage(
        self,
        user_id: str,
        task_id: str,
        task_stage: str,
        task_status: Optional[str] = None,
        task_summary: Optional[str] = None,
        structured_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "task_stage": task_stage,
            "last_active_at": self._now_string(),
        }
        if task_status:
            fields["task_status"] = task_status
        if task_summary:
            fields["task_summary"] = task_summary
        if structured_context is not None:
            fields["structured_context_json"] = structured_context
        return self._repo.update_task(user_id=user_id, task_id=task_id, **fields)

    def record_tool_called(self, user_id: str, task_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        stage = self._infer_stage_from_tool(tool_name)
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            last_tool_name=tool_name,
            task_stage=stage,
            last_active_at=self._now_string(),
        )

    def record_tool_output(self, user_id: str, task_id: str, tool_name: str, output_text: str) -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            last_tool_name=tool_name,
            last_tool_result_json={
                "tool_name": tool_name,
                "output_preview": str(output_text or "")[:1000],
            },
            last_active_at=self._now_string(),
        )

    def record_tool_failure(self, user_id: str, task_id: str, failure) -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_stage="tool_failed",
            last_tool_name=failure.tool_name,
            last_error=failure.developer_message,
            last_tool_result_json={
                "tool_name": failure.tool_name,
                "failure_category": failure.category.value,
                "failure_action": failure.action.value,
                "error_code": failure.error_code,
                "user_message": failure.user_message,
                "raw_preview": failure.raw_preview,
            },
            last_active_at=self._now_string(),
        )

    def mark_waiting_approval(self, user_id: str, task_id: str, approval_token: str, details: str = "") -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="waiting_approval",
            task_stage="waiting_human_approval",
            waiting_approval_token=approval_token,
            last_tool_result_json={"approval_details": details},
            last_active_at=self._now_string(),
        )

    def mark_resumed_after_approval(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="active",
            task_stage="resuming_after_approval",
            waiting_approval_token=None,
            last_active_at=self._now_string(),
        )

    def mark_retrying(self, user_id: str, task_id: str, error: str) -> Optional[Dict[str, Any]]:
        task = self._repo.get_task_by_id(user_id=user_id, task_id=task_id)
        retry_count = int((task or {}).get("retry_count") or 0) + 1
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="retrying",
            task_stage="retrying",
            last_error=error,
            retry_count=retry_count,
            last_active_at=self._now_string(),
        )

    def mark_blocked(self, user_id: str, task_id: str, error: str) -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="blocked",
            task_stage="blocked",
            last_error=error,
            last_active_at=self._now_string(),
        )

    def mark_completed(self, user_id: str, task_id: str, summary: str = "") -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="completed",
            task_stage="finished",
            task_summary=summary or "",
            waiting_approval_token=None,
            last_active_at=self._now_string(),
        )

    def mark_cancelled(self, user_id: str, task_id: str, reason: str = "") -> Optional[Dict[str, Any]]:
        return self._repo.update_task(
            user_id=user_id,
            task_id=task_id,
            task_status="cancelled",
            task_stage="cancelled",
            last_error=reason or None,
            waiting_approval_token=None,
            last_active_at=self._now_string(),
        )

    def find_task_by_approval_token(self, user_id: str, session_id: str, token: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_task_by_approval_token(user_id=user_id, session_id=session_id or "", token=token)

    def list_tasks(self, user_id: str, session_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        return self._repo.list_tasks(user_id=user_id, session_id=session_id or "", limit=limit)

    def get_task(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_task_by_id(user_id=user_id, task_id=task_id)

    @staticmethod
    def _now_string() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _infer_stage_from_tool(tool_name: str) -> str:
        if "service" in tool_name or "station" in tool_name:
            return "service_station_querying"
        if "knowledge" in tool_name:
            return "knowledge_querying"
        if "technical" in tool_name:
            return "diagnosis_running"
        return "tool_running"


task_memory_service = TaskMemoryService()
