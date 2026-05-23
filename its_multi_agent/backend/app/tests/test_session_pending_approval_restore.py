import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.session_service import session_service


def test_get_all_sessions_memory_includes_pending_approval_payload(monkeypatch):
    monkeypatch.setattr(
        session_service._repo,
        "get_all_sessions_metadata",
        lambda user_id: [
            (
                "s1",
                "2026-05-15 12:00:00",
                {
                    "system_messages": [{"role": "system", "content": "base system"}],
                    "messages": [{"role": "assistant", "content": "是否允许智能体查询维修站并继续执行？"}],
                },
            )
        ],
    )
    monkeypatch.setattr(
        "services.task_memory_service.task_memory_service.get_active_task",
        lambda user_id, session_id: {
            "task_status": "waiting_approval",
            "waiting_approval_token": "token-1",
            "last_tool_result_json": {"approval_details": "待执行请求：查询附近维修站"},
        },
    )
    monkeypatch.setattr(
        "services.hitl_service.hitl_service.get_pending_approval",
        lambda token: SimpleNamespace(
            token="token-1",
            title="需要人工确认",
            question="是否允许智能体查询维修站并继续执行？",
            details="待执行请求：查询附近维修站",
            approve_label="允许查询",
            reject_label="取消操作",
        ),
    )

    sessions = session_service.get_all_sessions_memory("u1")

    assert sessions[0]["pending_approval"]["token"] == "token-1"
    assert sessions[0]["pending_approval"]["question"] == "是否允许智能体查询维修站并继续执行？"
    assert sessions[0]["pending_approval"]["approveLabel"] == "允许查询"
