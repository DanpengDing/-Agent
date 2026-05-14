import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import routers


def test_task_memory_api_endpoints(monkeypatch):
    monkeypatch.setattr(
        "api.routers.task_memory_service.get_active_task",
        lambda user_id, session_id: {"task_id": "task-1", "task_status": "active"},
    )
    monkeypatch.setattr(
        "api.routers.task_memory_service.list_tasks",
        lambda user_id, session_id="", limit=20: [{"task_id": "task-1"}, {"task_id": "task-2"}],
    )
    monkeypatch.setattr(
        "api.routers.task_memory_service.get_task",
        lambda user_id, task_id: {"task_id": task_id, "task_status": "blocked"},
    )

    active = routers.get_active_task(user_id="u1", session_id="s1")
    assert active["success"] is True
    assert active["item"]["task_id"] == "task-1"

    listing = routers.get_task_memories(user_id="u1", session_id="s1", limit=20)
    assert listing["success"] is True
    assert listing["total"] == 2

    detail = routers.get_task_memory_detail(task_id="task-2", user_id="u1")
    assert detail["success"] is True
    assert detail["item"]["task_id"] == "task-2"
