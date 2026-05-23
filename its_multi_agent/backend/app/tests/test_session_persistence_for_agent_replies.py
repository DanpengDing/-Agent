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
from schemas.tool_failure import ToolFailure, ToolFailureAction, ToolFailureCategory
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


def _extract_sse_packets(chunks):
    packets = []
    for chunk in chunks:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        if not chunk.startswith("data: "):
            continue
        payload = chunk[len("data: "):].strip()
        if payload:
            packets.append(json.loads(payload))
    return packets


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
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda rewrite_result: "")
    monkeypatch.setattr("services.agent_service.Runner.run_streamed", lambda **kwargs: _FakeStreamingResult(interruptions=[object()]))
    monkeypatch.setattr("services.agent_service.build_service_station_approval_details", lambda query: "Need location before continuing.")
    monkeypatch.setattr(
        "services.agent_service.hitl_service.create_pending_approval",
        lambda **kwargs: SimpleNamespace(
            token="token-1",
            title="Human approval",
            question="Continue the lookup?",
            details=kwargs.get("details"),
            approve_label="Continue",
            reject_label="Cancel",
        ),
    )

    request = ChatMessageRequest(
        query="Find a repair station",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages
    assert "Continue the lookup?" in assistant_messages[-1]["content"]


def test_human_approval_persists_reviewed_answer_and_metadata_in_session(monkeypatch):
    saved_states = []
    base_state = SessionMemoryState()
    task = {
        "task_id": "task-1",
        "task_type": "technical_consult",
        "last_tool_result_json": {
            "tool_name": "query_knowledge",
            "evidence_items": [
                {
                    "title": "KB Evidence",
                    "snippet": "The available documentation only supports gathering more location details first.",
                    "source": "knowledge_base",
                }
            ],
        },
    }

    approval = SimpleNamespace(
        token="token-1",
        decision="approved",
        state=SimpleNamespace(approve=lambda interruption: None),
        interruptions=[],
        query="Find a repair station",
    )

    async def fake_run(agent, state):
        return SimpleNamespace(final_output=json.dumps({"answer": "Give me your location.", "references": ["knowledge_base"]}))

    monkeypatch.setattr("api.routers.Runner.run", fake_run)
    monkeypatch.setattr("api.routers.hitl_service.resolve_pending_approval", lambda **kwargs: approval)
    monkeypatch.setattr("api.routers.hitl_service.consume_approval", lambda token: None)
    monkeypatch.setattr("api.routers.extract_backend_error_details_from_result", lambda result: [])
    monkeypatch.setattr("api.routers.task_memory_service.find_task_by_approval_token", lambda **kwargs: task)
    monkeypatch.setattr("api.routers.task_memory_service.mark_resumed_after_approval", lambda **kwargs: None)
    monkeypatch.setattr("api.routers.task_memory_service.mark_completed", lambda **kwargs: None)
    monkeypatch.setattr(session_service, "load_session_state", lambda user_id, session_id: base_state)
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))

    request = HumanApprovalRequest(
        approval_token="token-1",
        decision="approved",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    response = asyncio.run(routers.human_approval(request))
    assert isinstance(response, StreamingResponse)

    chunks = []

    async def consume():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]
    packets = _extract_sse_packets(chunks)
    answer_packets = [packet for packet in packets if packet.get("content", {}).get("kind") == "ANSWER"]

    assert assistant_messages
    assert answer_packets
    assert assistant_messages[-1]["content"] == "Give me your location."
    assert assistant_messages[-1]["review_verdict"]["status"] == "supported"
    assert assistant_messages[-1]["evidence_cards"][0]["title"] == "KB Evidence"
    assert answer_packets[-1]["content"]["review_verdict"]["status"] == "supported"
    assert answer_packets[-1]["content"]["evidence_cards"][0]["title"] == "KB Evidence"


def test_process_task_persists_classified_failure_message_in_session(monkeypatch):
    saved_states = []
    base_state = SessionMemoryState()
    failure = ToolFailure(
        tool_name="query_knowledge",
        category=ToolFailureCategory.UNKNOWN,
        action=ToolFailureAction.BLOCK_TASK,
        error_code="unknown_error",
        developer_message="bug",
        user_message="The tool failed and the request cannot continue automatically.",
        retryable=False,
        raw_preview="bug",
    )

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    class _FailureStreamingResult:
        interruptions = []
        final_output = ""

        async def stream_events(self):
            if False:
                yield None

    async def fake_process_stream_response(result, callbacks=None):
        if callbacks and callbacks.get("on_tool_failure"):
            callbacks["on_tool_failure"](failure)
        if False:
            yield None

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.task_memory_service.ensure_task", lambda *args, **kwargs: {"task_id": "task-1", "task_type": "service_station_lookup"})
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_called", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_output", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.mark_blocked", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.get_task", lambda *args, **kwargs: {"last_tool_name": "query_knowledge"})
    monkeypatch.setattr("services.agent_service.Runner.run_streamed", lambda **kwargs: _FailureStreamingResult())
    monkeypatch.setattr("services.agent_service.process_stream_response", fake_process_stream_response)

    request = ChatMessageRequest(
        query="Trigger a failure message",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages
    assert "cannot continue automatically" in assistant_messages[-1]["content"]


def test_append_and_save_message_preserves_extra_fields(monkeypatch):
    saved_states = []
    base_state = SessionMemoryState()

    monkeypatch.setattr(session_service, "load_session_state", lambda user_id, session_id: base_state)
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))

    session_service.append_and_save_message(
        user_id="u1",
        session_id="s1",
        role="assistant",
        content="Need more verification.",
        extra_fields={
            "review_verdict": {"status": "review_unavailable"},
            "evidence_cards": [{"title": "Evidence 1"}],
        },
    )

    saved_messages = _collect_saved_messages(saved_states)

    assert saved_messages[-1]["content"] == "Need more verification."
    assert saved_messages[-1]["review_verdict"]["status"] == "review_unavailable"
    assert saved_messages[-1]["evidence_cards"][0]["title"] == "Evidence 1"
