import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.request import ChatMessageRequest, UserContext
from schemas.session_memory import SessionMemoryState
from services.agent_service import MultiAgentService
from services.session_service import session_service


class _FakeStreamingResult:
    def __init__(self, final_output="恢复后的回答"):
        self.interruptions = []
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None


def test_process_task_injects_resume_task_context(monkeypatch):
    captured = {"history": None}
    active_task = {
        "task_id": "task-1",
        "task_type": "service_station_lookup",
        "task_goal": "查询最近维修站",
        "task_status": "blocked",
        "task_stage": "service_station_querying",
        "last_tool_name": "query_service_station_and_navigate",
        "last_tool_result_json": {"output_preview": "地图鉴权失败"},
        "last_error": "地图鉴权失败",
        "waiting_approval_token": None,
    }

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return SessionMemoryState()

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [{"role": "system", "content": "base"}])
    monkeypatch.setattr(session_service, "append_message_to_state", lambda state, role, content: state)
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.task_memory_service.ensure_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: active_task)
    monkeypatch.setattr("services.agent_service.task_memory_service.build_resume_system_messages", lambda task: [{"role": "system", "content": "【任务状态记忆】"}])
    monkeypatch.setattr("services.agent_service.process_stream_response", lambda result, callbacks=None: _empty_stream())
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: captured.update({"history": kwargs["input"]}) or _FakeStreamingResult(),
    )
    monkeypatch.setattr("services.agent_service.structured_output_service.parse_final_output", lambda output: SimpleNamespace(answer=output, intent="general"))

    request = ChatMessageRequest(
        query="继续查维修站",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    assert captured["history"][1]["content"] == "【任务状态记忆】"


async def _empty_stream():
    if False:
        yield None
