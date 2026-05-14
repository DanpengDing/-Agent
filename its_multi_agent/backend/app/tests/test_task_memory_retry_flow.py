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


def test_process_task_marks_retrying_then_blocked_on_second_failure(monkeypatch):
    calls = []

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return SessionMemoryState()

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "append_message_to_state", lambda state, role, content: state)
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr(
        "services.agent_service.task_memory_service.ensure_task",
        lambda *args, **kwargs: {"task_id": "task-1", "task_type": "service_station_lookup"},
    )
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "services.agent_service.task_memory_service.mark_retrying",
        lambda user_id, task_id, error: calls.append(("retrying", task_id, error)),
    )
    monkeypatch.setattr(
        "services.agent_service.task_memory_service.mark_blocked",
        lambda user_id, task_id, error: calls.append(("blocked", task_id, error)),
    )
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("temporary failure")),
    )

    request = ChatMessageRequest(
        query="帮我查维修站",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    assert calls[0][0] == "retrying"
    assert calls[-1][0] == "blocked"
