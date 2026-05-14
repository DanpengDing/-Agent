import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import routers
from schemas.request import UserPreferenceUpsertRequest


def test_memory_api_preference_crud(monkeypatch):
    store = {"items": [{"memory_key": "reply.style", "memory_value": "简洁", "memory_type": "manual"}]}

    monkeypatch.setattr("api.routers.memory_service.list_long_term_memories", lambda user_id, limit=20: [])
    monkeypatch.setattr("api.routers.memory_service.list_user_preferences", lambda user_id, limit=20: store["items"])
    monkeypatch.setattr(
        "api.routers.memory_service.set_user_preference",
        lambda user_id, preference_key, preference_value, session_id="", preference_type="manual": store["items"].append(
            {"memory_key": preference_key, "memory_value": preference_value, "memory_type": preference_type}
        ),
    )
    monkeypatch.setattr("api.routers.memory_service.delete_user_preference", lambda user_id, preference_key: 1)

    get_result = routers.get_user_preferences(user_id="u1", limit=20)
    assert get_result["success"] is True
    assert get_result["items"][0]["memory_key"] == "reply.style"

    put_result = routers.upsert_user_preference(
        UserPreferenceUpsertRequest(
            user_id="u1",
            preference_key="repair.priority",
            preference_value="官方售后",
            session_id="s1",
        )
    )
    assert put_result["success"] is True
    assert put_result["preference_key"] == "repair.priority"

    delete_result = routers.delete_user_preference(preference_key="reply.style", user_id="u1")
    assert delete_result["success"] is True
    assert delete_result["deleted"] == 1
