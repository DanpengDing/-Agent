from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

from models import ChatMessage, ChatSession


class RedisSessionRepository(ABC):
    # Redis 只负责保存热点消息，目标是降低每轮请求的读取延迟。
    @abstractmethod
    async def get_recent_messages(self, session_id: str) -> list[ChatMessage] | None:
        raise NotImplementedError

    @abstractmethod
    async def save_recent_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def trim_recent_messages(self, session_id: str, keep_last: int) -> None:
        raise NotImplementedError


class MySQLSessionRepository(ABC):
    # MySQL 负责最终持久化，是会话数据的事实来源。
    @abstractmethod
    async def get_or_create_session(self, user_id: str, session_id: str) -> ChatSession:
        raise NotImplementedError

    @abstractmethod
    async def load_recent_messages(self, session_id: str, limit: int) -> list[ChatMessage]:
        raise NotImplementedError

    @abstractmethod
    async def append_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def touch_session(self, session_id: str, updated_at: datetime) -> None:
        raise NotImplementedError


class InMemoryRedisSessionRepository(RedisSessionRepository):
    # 内存版 Redis 仓储，只用于演示缓存命中和回填链路。
    def __init__(self) -> None:
        self._store: dict[str, list[ChatMessage]] = {}

    async def get_recent_messages(self, session_id: str) -> list[ChatMessage] | None:
        messages = self._store.get(session_id)
        return copy.deepcopy(messages) if messages is not None else None

    async def save_recent_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        self._store[session_id] = copy.deepcopy(messages)

    async def trim_recent_messages(self, session_id: str, keep_last: int) -> None:
        if session_id in self._store:
            self._store[session_id] = self._store[session_id][-keep_last:]


class InMemoryMySQLSessionRepository(MySQLSessionRepository):
    # 内存版 MySQL 仓储，用来表达回源查询和持久化接口。
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._messages: dict[str, list[ChatMessage]] = defaultdict(list)

    async def get_or_create_session(self, user_id: str, session_id: str) -> ChatSession:
        session = self._sessions.get(session_id)
        if session:
            return copy.deepcopy(session)

        # 示例里首次请求自动建会话，方便直接跑通链路。
        now = datetime.utcnow()
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            title="新会话",
            created_at=now,
            updated_at=now,
        )
        self._sessions[session_id] = session
        return copy.deepcopy(session)

    async def load_recent_messages(self, session_id: str, limit: int) -> list[ChatMessage]:
        return copy.deepcopy(self._messages[session_id][-limit:])

    async def append_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        self._messages[session_id].extend(copy.deepcopy(messages))

    async def touch_session(self, session_id: str, updated_at: datetime) -> None:
        # updated_at 一般用于最近会话排序和后台列表展示。
        if session_id in self._sessions:
            self._sessions[session_id].updated_at = updated_at
