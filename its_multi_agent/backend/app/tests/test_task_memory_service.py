import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.task_memory_service import TaskMemoryService


class _FakeTaskMemoryRepository:
    def __init__(self):
        self.tasks = {}
        self.counter = 0

    def create_task(self, **kwargs):
        self.counter += 1
        task = {
            "task_id": f"task-{self.counter}",
            "retry_count": 0,
            "last_tool_name": None,
            "last_tool_result_json": None,
            "last_error": None,
            "waiting_approval_token": None,
            **kwargs,
        }
        self.tasks[(kwargs["user_id"], task["task_id"])] = task
        return task

    def get_active_task(self, user_id, session_id):
        items = [
            task
            for (uid, _), task in self.tasks.items()
            if uid == user_id and task["session_id"] == session_id and task["task_status"] in {"active", "waiting_approval", "blocked", "retrying"}
        ]
        items.sort(key=lambda item: item["task_id"])
        return items[0] if items else None

    def update_task(self, user_id, task_id, **fields):
        task = self.tasks[(user_id, task_id)]
        task.update(fields)
        return task

    def get_task_by_id(self, user_id, task_id):
        return self.tasks.get((user_id, task_id))

    def get_task_by_approval_token(self, user_id, session_id, token):
        for (uid, _), task in self.tasks.items():
            if uid == user_id and task["session_id"] == session_id and task.get("waiting_approval_token") == token:
                return task
        return None

    def list_tasks(self, user_id, session_id="", limit=20):
        items = [task for (uid, _), task in self.tasks.items() if uid == user_id]
        if session_id:
            items = [task for task in items if task["session_id"] == session_id]
        return items[:limit]


def test_ensure_task_creates_service_station_task():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)

    task = service.ensure_task("u1", "s1", "帮我查最近的维修站")

    assert task is not None
    assert task["task_type"] == "service_station_lookup"
    assert task["task_stage"] == "intent_routed"


def test_should_resume_task_for_waiting_approval_and_continuation_phrase():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)
    task = repo.create_task(
        user_id="u1",
        session_id="s1",
        task_type="service_station_lookup",
        task_goal="查维修站",
        task_status="waiting_approval",
        task_stage="waiting_human_approval",
        task_summary="查维修站",
        structured_context={"a": 1},
        priority=0,
    )

    assert service.should_resume_task(task, "我同意")
    task["task_status"] = "blocked"
    assert service.should_resume_task(task, "继续")


def test_waiting_approval_task_does_not_hijack_unrelated_new_query():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)
    task = repo.create_task(
        user_id="u1",
        session_id="s1",
        task_type="service_station_lookup",
        task_goal="查维修站",
        task_status="waiting_approval",
        task_stage="waiting_human_approval",
        task_summary="查维修站",
        structured_context={"a": 1},
        priority=0,
    )

    assert service.should_resume_task(task, "我同意")
    assert not service.should_resume_task(task, "电脑蓝屏了怎么办")


def test_mark_retrying_increments_retry_count():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)
    task = repo.create_task(
        user_id="u1",
        session_id="s1",
        task_type="service_station_lookup",
        task_goal="查维修站",
        task_status="active",
        task_stage="intent_routed",
        task_summary="查维修站",
        structured_context={},
        priority=0,
    )

    updated = service.mark_retrying("u1", task["task_id"], "temporary error")

    assert updated["task_status"] == "retrying"
    assert updated["retry_count"] == 1
    assert updated["last_error"] == "temporary error"


def test_build_resume_system_messages_contains_task_context():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)
    message = service.build_resume_system_messages(
        {
            "task_type": "service_station_lookup",
            "task_goal": "查询最近维修站",
            "task_status": "blocked",
            "task_stage": "service_station_querying",
            "last_tool_name": "query_service_station_and_navigate",
            "last_tool_result_json": {"output_preview": "地图鉴权失败"},
            "last_error": "地图鉴权失败",
            "waiting_approval_token": None,
        }
    )[0]["content"]

    assert "任务类型：service_station_lookup" in message
    assert "最近工具：query_service_station_and_navigate" in message
    assert "地图鉴权失败" in message


def test_ensure_task_cancels_old_incompatible_active_task_before_creating_new_one():
    repo = _FakeTaskMemoryRepository()
    service = TaskMemoryService(repository=repo)
    old_task = repo.create_task(
        user_id="u1",
        session_id="s1",
        task_type="service_station_lookup",
        task_goal="查维修站",
        task_status="active",
        task_stage="service_station_querying",
        task_summary="查维修站",
        structured_context={},
        priority=0,
    )

    new_task = service.ensure_task("u1", "s1", "电脑蓝屏了")

    assert new_task is not None
    assert new_task["task_type"] == "technical_consult"
    assert repo.get_task_by_id("u1", old_task["task_id"])["task_status"] == "cancelled"
