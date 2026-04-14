from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    # 统一消息角色，便于在 Redis、MySQL 和 LLM 上下文之间复用。
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(slots=True)
class ChatMessage:
    # 单条消息实体，既可以写入 MySQL，也可以作为 Redis 热数据缓存。
    message_id: str
    session_id: str
    role: MessageRole
    content: str
    sequence: int
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatSession:
    # 会话主记录，对应持久化层里的 chat_session 表。
    session_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    summary: str | None = None


@dataclass(slots=True)
class RuntimeContext:
    # 运行时上下文，history 已经是可以直接交给 LLM 的格式。
    session: ChatSession
    history: list[dict[str, str]]
    cache_hit: bool
