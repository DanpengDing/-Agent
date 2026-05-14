import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from starlette.responses import StreamingResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import routers
from schemas.request import HumanApprovalRequest, UserContext


def test_human_approval_updates_task_memory_states(monkeypatch):
    calls = []
    approval = SimpleNamespace(
        token="token-1",
        decision="approved",
        state=SimpleNamespace(approve=lambda interruption: None),
        interruptions=[],
        query="我要去维修站",
    )

    async def fake_run(agent, state):
        return SimpleNamespace(final_output='{"answer":"已为你继续查询维修站"}')

    monkeypatch.setattr("api.routers.Runner.run", fake_run)
    monkeypatch.setattr("api.routers.hitl_service.resolve_pending_approval", lambda **kwargs: approval)
    monkeypatch.setattr("api.routers.hitl_service.consume_approval", lambda token: None)
    monkeypatch.setattr("api.routers.extract_backend_error_details_from_result", lambda result: [])
    monkeypatch.setattr("api.routers.task_memory_service.find_task_by_approval_token", lambda user_id, session_id, token: {"task_id": "task-1"})
    monkeypatch.setattr("api.routers.task_memory_service.mark_resumed_after_approval", lambda user_id, task_id: calls.append(("resumed", task_id)))
    monkeypatch.setattr("api.routers.task_memory_service.mark_completed", lambda user_id, task_id, summary='': calls.append(("completed", task_id, summary)))
    monkeypatch.setattr("api.routers.session_service.append_and_save_message", lambda *args, **kwargs: None)

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

    assert ("resumed", "task-1") in calls
    assert any(item[0] == "completed" for item in calls)
