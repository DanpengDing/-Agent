from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

from models import ChatMessage, MessageRole, RuntimeContext
from repositories import MySQLSessionRepository, RedisSessionRepository


class SessionService:
    # 统一收口缓存查询、数据库回源和一轮对话落库逻辑。
    def __init__(
        self,
        redis_repo: RedisSessionRepository,
        mysql_repo: MySQLSessionRepository,
        history_limit: int = 10,
    ) -> None:
        self.redis_repo = redis_repo
        self.mysql_repo = mysql_repo
        self.history_limit = history_limit

    async def build_runtime_context(
        self,
        user_id: str,
        session_id: str,
        user_query: str,
    ) -> RuntimeContext:
        # 先保证当前请求已经绑定到一个合法会话。
        session = await self.mysql_repo.get_or_create_session(user_id, session_id)

        # 主链路优先查 Redis，尽量把上下文读取延迟压低。
        recent_messages = await self.redis_repo.get_recent_messages(session_id)
        cache_hit = recent_messages is not None

        if recent_messages is None:
            # 缓存未命中时回源 MySQL，并把结果重新写回 Redis。
            recent_messages = await self.mysql_repo.load_recent_messages(
                session_id=session_id,
                limit=self.history_limit,
            )
            await self.redis_repo.save_recent_messages(session_id, recent_messages)

        # 在这里统一转换成 LLM 可直接消费的 role/content 结构。
        history = self._to_llm_history(recent_messages)
        history.append({"role": "user", "content": user_query})

        return RuntimeContext(
            session=session,
            history=history,
            cache_hit=cache_hit,
        )

    async def persist_round(
        self,
        user_id: str,
        session_id: str,
        user_query: str,
        assistant_answer: str,
    ) -> None:
        session = await self.mysql_repo.get_or_create_session(user_id, session_id)
        recent_messages = await self.redis_repo.get_recent_messages(session_id) or []
        next_sequence = recent_messages[-1].sequence + 1 if recent_messages else 1
        now = datetime.utcnow()

        # 一轮完整对话至少会新增 user 和 assistant 两条消息。
        round_messages = [
            ChatMessage(
                message_id=str(uuid4()),
                session_id=session_id,
                role=MessageRole.USER,
                content=user_query,
                sequence=next_sequence,
                created_at=now,
            ),
            ChatMessage(
                message_id=str(uuid4()),
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=assistant_answer,
                sequence=next_sequence + 1,
                created_at=now,
            ),
        ]

        # 先更新 Redis，保证下一轮请求能立刻拿到最新上下文。
        merged_messages = recent_messages + round_messages
        await self.redis_repo.save_recent_messages(session_id, merged_messages)
        await self.redis_repo.trim_recent_messages(session_id, self.history_limit)

        # MySQL 改成异步刷盘，避免数据库写入阻塞流式响应。
        asyncio.create_task(self._persist_to_mysql(session.session_id, round_messages, now))

    async def _persist_to_mysql(
        self,
        session_id: str,
        round_messages: list[ChatMessage],
        updated_at: datetime,
    ) -> None:
        # 生产环境里这里通常会替换成消息队列消费者或后台任务。
        await self.mysql_repo.append_messages(session_id, round_messages)
        await self.mysql_repo.touch_session(session_id, updated_at)

    @staticmethod
    def _to_llm_history(messages: list[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": item.role.value, "content": item.content} for item in messages]
