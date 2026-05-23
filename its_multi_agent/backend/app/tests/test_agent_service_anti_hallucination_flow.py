import asyncio
import json
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
    interruptions = []

    def __init__(self, final_output):
        self.final_output = final_output

    async def stream_events(self):
        if False:
            yield None


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


def test_process_task_downgrades_high_risk_answer_before_persistence(monkeypatch):
    saved_states = []
    completed_summaries = []
    base_state = SessionMemoryState()

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    async def fake_process_stream_response(result, callbacks=None):
        if False:
            yield None

    task = {
        "task_id": "task-1",
        "task_type": "technical_consult",
        "last_tool_result_json": {
            "tool_name": "query_knowledge",
            "evidence_items": [
                {
                    "title": "Blue Screen Basics",
                    "snippet": "The common causes are driver issues and corrupted system files, so software checks should come first.",
                    "source": "knowledge_base",
                }
            ],
        },
    }

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.ensure_task", lambda *args, **kwargs: task)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_called", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_output", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.get_task", lambda *args, **kwargs: task)
    monkeypatch.setattr(
        "services.agent_service.task_memory_service.mark_completed",
        lambda user_id, task_id, summary="": completed_summaries.append(summary),
    )
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: _FakeStreamingResult(
            json.dumps(
                {
                    "answer": "You must replace the motherboard.",
                    "references": ["knowledge_base"],
                }
            )
        ),
    )
    monkeypatch.setattr("services.agent_service.process_stream_response", fake_process_stream_response)

    request = ChatMessageRequest(
        query="What should I do about a blue screen?",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages
    assert assistant_messages[-1]["content"] != "You must replace the motherboard."
    assert assistant_messages[-1]["review_verdict"]["status"] == "unsupported"
    assert assistant_messages[-1]["evidence_cards"][0]["title"] == "Blue Screen Basics"
    assert completed_summaries[-1] == assistant_messages[-1]["content"]


def test_process_task_falls_back_when_review_service_errors(monkeypatch):
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
                    "snippet": "The documentation only supports software troubleshooting first.",
                    "source": "knowledge_base",
                }
            ],
        },
    }

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    async def fake_process_stream_response(result, callbacks=None):
        if False:
            yield None

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "save_session_state", lambda user_id, session_id, state: saved_states.append(state))
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.ensure_task", lambda *args, **kwargs: task)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_called", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_output", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.get_task", lambda *args, **kwargs: task)
    monkeypatch.setattr("services.agent_service.task_memory_service.mark_completed", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: _FakeStreamingResult(
            json.dumps({"answer": "You must replace the motherboard.", "references": ["knowledge_base"]})
        ),
    )
    monkeypatch.setattr("services.agent_service.process_stream_response", fake_process_stream_response)
    monkeypatch.setattr(
        "services.agent_service.answer_review_service.review_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("review exploded")),
    )

    request = ChatMessageRequest(
        query="What should I do about a blue screen?",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for _ in MultiAgentService.process_task(request, flag=True):
            pass

    asyncio.run(consume())

    saved_messages = _collect_saved_messages(saved_states)
    assistant_messages = [msg for msg in saved_messages if msg.get("role") == "assistant"]

    assert assistant_messages
    assert assistant_messages[-1]["content"] != "You must replace the motherboard."
    assert assistant_messages[-1]["review_verdict"]["status"] == "review_unavailable"


def test_process_task_emits_finalized_answer_packet_with_evidence_cards(monkeypatch):
    base_state = SessionMemoryState()
    task = {
        "task_id": "task-1",
        "task_type": "technical_consult",
        "last_tool_result_json": {
            "tool_name": "query_knowledge",
            "evidence_items": [
                {
                    "title": "Blue Screen Basics",
                    "snippet": "The common causes are driver issues and corrupted system files, so software checks should come first.",
                    "source": "knowledge_base",
                    "uri": "kb://blue-screen-basics",
                }
            ],
        },
    }

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return base_state

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    async def fake_process_stream_response(result, callbacks=None):
        if False:
            yield None

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.task_memory_service.get_active_task_for_query", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.ensure_task", lambda *args, **kwargs: task)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_called", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_output", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.record_tool_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.task_memory_service.get_task", lambda *args, **kwargs: task)
    monkeypatch.setattr("services.agent_service.task_memory_service.mark_completed", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "services.agent_service.Runner.run_streamed",
        lambda **kwargs: _FakeStreamingResult(
            json.dumps(
                {
                    "answer": "You should start by checking software and driver issues.",
                    "references": ["knowledge_base"],
                }
            )
        ),
    )
    monkeypatch.setattr("services.agent_service.process_stream_response", fake_process_stream_response)

    request = ChatMessageRequest(
        query="What should I do about a blue screen?",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    chunks = []

    async def consume():
        async for chunk in MultiAgentService.process_task(request, flag=True):
            chunks.append(chunk)

    asyncio.run(consume())

    packets = _extract_sse_packets(chunks)
    answer_packets = [packet for packet in packets if packet.get("content", {}).get("kind") == "ANSWER"]

    assert answer_packets
    assert answer_packets[-1]["content"]["evidence_cards"][0]["title"] == "Blue Screen Basics"
    assert answer_packets[-1]["content"]["evidence_cards"][0]["uri"] == "kb://blue-screen-basics"
