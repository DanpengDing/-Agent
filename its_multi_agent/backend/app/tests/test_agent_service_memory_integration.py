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
    def __init__(self, final_output="测试回答"):
        self.interruptions = []
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None


def test_process_task_injects_memory_messages_and_captures_user_memory(monkeypatch):
    captured = {"memory_text": None, "history": None}
    base_state = SessionMemoryState()

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    def fake_build_runtime_history(*args, **kwargs):
        return [{"role": "system", "content": "base system"}]

    def fake_capture_user_memory(user_id, session_id, text):
        captured["memory_text"] = text

    def fake_build_memory_system_messages(user_id):
        return [{"role": "system", "content": "【长期记忆】\n- profile.current_location: 晋江市陈埭镇"}]

    def fake_run_streamed(**kwargs):
        captured["history"] = kwargs["input"]
        return _FakeStreamingResult()

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", fake_build_runtime_history)
    monkeypatch.setattr(session_service, "append_message_to_state", lambda state, role, content: state)
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", fake_capture_user_memory)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", fake_build_memory_system_messages)
    monkeypatch.setattr("services.agent_service.process_stream_response", lambda result, callbacks=None: _empty_stream())
    monkeypatch.setattr("services.agent_service.Runner.run_streamed", fake_run_streamed)
    monkeypatch.setattr(
        "services.agent_service.structured_output_service.parse_final_output",
        lambda output: SimpleNamespace(answer=output, intent="general"),
    )

    request = ChatMessageRequest(
        query="我在晋江市陈埭镇，帮我找维修站",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    assert captured["memory_text"] == "我在晋江市陈埭镇，帮我找维修站"
    assert captured["history"] is not None
    assert captured["history"][0]["content"] == "base system"
    assert "【长期记忆】" in captured["history"][1]["content"]


async def _empty_stream():
    if False:
        yield None
