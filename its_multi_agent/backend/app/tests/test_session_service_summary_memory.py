import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.session_memory import ConversationSummary, SessionMemoryState
from services.session_service import session_service


def test_load_runtime_state_persists_summary_memory_when_compression_triggers(monkeypatch):
    captured = {}
    compressed_state = SessionMemoryState(
        summary=ConversationSummary(
            summary_text="用户住在晋江市陈埭镇",
            facts=["用户住在晋江市陈埭镇"],
        )
    )

    monkeypatch.setattr(session_service, "load_session_state", lambda user_id, session_id: SessionMemoryState())
    monkeypatch.setattr(
        "services.session_service.context_compression_service.compress_state_if_needed",
        _fake_compress_result(compressed_state),
    )
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "services.memory_service.memory_service.capture_summary_memory",
        lambda user_id, session_id, summary: captured.update(
            {"user_id": user_id, "session_id": session_id, "summary_text": summary.summary_text}
        ),
    )

    state = asyncio.run(session_service.load_runtime_state("u1", "s1", "我要修电脑"))

    assert state.summary is not None
    assert captured["user_id"] == "u1"
    assert captured["session_id"] == "s1"
    assert captured["summary_text"] == "用户住在晋江市陈埭镇"


def _fake_compress_result(state):
    async def _inner(*args, **kwargs):
        return state, True, True

    return _inner
