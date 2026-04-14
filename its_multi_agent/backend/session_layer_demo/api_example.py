from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from repositories import InMemoryMySQLSessionRepository, InMemoryRedisSessionRepository
from session_service import SessionService


app = FastAPI(title="Session Layer Demo")

# 这里用内存仓储代替真实 Redis/MySQL，让示例保持自包含。
redis_repo = InMemoryRedisSessionRepository()
mysql_repo = InMemoryMySQLSessionRepository()
session_service = SessionService(redis_repo=redis_repo, mysql_repo=mysql_repo)


class UserContext(BaseModel):
    user_id: str
    session_id: str


class ChatRequest(BaseModel):
    query: str
    context: UserContext


async def fake_agent_stream(query: str) -> AsyncGenerator[str, None]:
    # 用假流式输出模拟 Agent 执行，重点突出会话分层而不是模型细节。
    chunks = [
        {"kind": "PROCESS", "text": "已加载会话上下文"},
        {"kind": "PROCESS", "text": "已完成路由，进入执行链路"},
        {"kind": "ANSWER", "text": f"这是对问题“{query}”的示例回答。"},
    ]
    for chunk in chunks:
        yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
    yield "data: " + json.dumps({"kind": "FINISH"}, ensure_ascii=False) + "\n\n"


@app.post("/api/query")
async def query(request: ChatRequest) -> StreamingResponse:
    # 进入 Agent 之前，先统一组装运行时上下文。
    runtime_context = await session_service.build_runtime_context(
        user_id=request.context.user_id,
        session_id=request.context.session_id,
        user_query=request.query,
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        assistant_answer = ""

        # 先把缓存命中情况吐给前端，便于观察 Redis 和 MySQL 的读取路径。
        yield "data: " + json.dumps(
            {
                "kind": "PROCESS",
                "text": "Redis命中" if runtime_context.cache_hit else "Redis未命中，已回源MySQL",
            },
            ensure_ascii=False,
        ) + "\n\n"

        async for item in fake_agent_stream(request.query):
            if "ANSWER" in item:
                assistant_answer = f"这是对问题“{request.query}”的示例回答。"
            yield item

        # 等流式输出完成后再持久化，避免数据库写入拖慢首包。
        await session_service.persist_round(
            user_id=request.context.user_id,
            session_id=request.context.session_id,
            user_query=request.query,
            assistant_answer=assistant_answer,
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
