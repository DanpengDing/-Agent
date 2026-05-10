import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from starlette.responses import StreamingResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import routers
from schemas.request import ChatMessageRequest, HumanApprovalRequest, UserContext
from schemas.session_memory import SessionMemoryState
from services.agent_service import MultiAgentService
from services.session_service import session_service


class _FakeStreamingResult:
    def __init__(self, interruptions=None, final_output=""):
        self.interruptions = interruptions or []
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None

    def to_state(self):
        return {"fake": "state"}


def _collect_saved_messages(saved_states):
    return [msg for state in saved_states for msg in state.messages]


def test_process_task_persists_approval_prompt_in_session(monkeypatch):
    saved_states = []
    base_state = SessionMemoryState()

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))
    monkeypatch.setattr(
        "services.agent_service.query_rewrite_service.rewrite",
        fake_rewrite,
    )
    monkeypatch.setattr(
        "services.agent_service.query_rewrite_service.build_process_message",
        lambda rewrite_result: "",
    )
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: _FakeStreamingResult(interruptions=[object()]),
    )
    monkeypatch.setattr(
        "services.agent_service.build_service_station_approval_details",
        lambda query: "需要定位后再继续",
    )
    monkeypatch.setattr(
        "services.agent_service.hitl_service.create_pending_approval",
        lambda **kwargs: SimpleNamespace(
            token="token-1",
            title="人工确认",
            question="是否继续查询服务站？",
            details=kwargs.get("details"),
            approve_label="继续",
            reject_label="取消",
        ),
    )

    request = ChatMessageRequest(
        query="我要修电脑",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages, "approval prompt should be persisted as an assistant message"
    assert "是否继续查询服务站" in assistant_messages[-1]["content"]


def test_human_approval_persists_final_answer_in_session(monkeypatch):
    saved_states = []
    base_state = SessionMemoryState()

    approval = SimpleNamespace(
        token="token-1",
        decision="approved",
        state=SimpleNamespace(approve=lambda interruption: None),
        interruptions=[],
        query="我要修电脑",
    )

    async def fake_run(agent, state):
        return SimpleNamespace(final_output=json.dumps({"answer": "请告诉我你所在的城市或具体地址"}))

    monkeypatch.setattr("api.routers.Runner.run", fake_run)
    monkeypatch.setattr("api.routers.hitl_service.resolve_pending_approval", lambda **kwargs: approval)
    monkeypatch.setattr("api.routers.hitl_service.consume_approval", lambda token: None)
    monkeypatch.setattr("api.routers.extract_backend_error_details_from_result", lambda result: [])
    monkeypatch.setattr(session_service, "load_session_state", lambda user_id, session_id: base_state)
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))

    request = HumanApprovalRequest(
        approval_token="token-1",
        decision="approved",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    response = asyncio.run(routers.human_approval(request))
    assert isinstance(response, StreamingResponse)

    async def consume():
        async for _ in response.body_iterator:
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages, "approved answer should be persisted as an assistant message"
    assert "请告诉我你所在的城市或具体地址" in assistant_messages[-1]["content"]
