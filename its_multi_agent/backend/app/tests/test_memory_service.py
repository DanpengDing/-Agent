import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.memory_service import MemoryService
from schemas.session_memory import ConversationSummary


class _FakeMemoryRepository:
    def __init__(self):
        self.long_term = {}
        self.preferences = {}

    def upsert_long_term_memory(
        self,
        user_id,
        memory_key,
        memory_value,
        memory_type="fact",
        topic="",
        confidence=0.8,
        source_session_id="",
        source_text="",
        metadata_json=None,
        expires_at=None,
    ):
        self.long_term[(user_id, memory_key)] = {
            "memory_key": memory_key,
            "memory_value": memory_value,
            "memory_type": memory_type,
            "topic": topic,
            "confidence": confidence,
            "source_session_id": source_session_id,
            "source_text": source_text,
        }

    def upsert_user_preference(
        self,
        user_id,
        preference_key,
        preference_value,
        preference_type="explicit",
        confidence=0.8,
        source_session_id="",
        source_text="",
        metadata_json=None,
    ):
        self.preferences[(user_id, preference_key)] = {
            "memory_key": preference_key,
            "memory_value": preference_value,
            "memory_type": preference_type,
            "confidence": confidence,
            "source_session_id": source_session_id,
            "source_text": source_text,
        }

    def list_long_term_memories(self, user_id, limit=20):
        return list(self.long_term.values())[:limit]

    def list_user_preferences(self, user_id, limit=20):
        return list(self.preferences.values())[:limit]

    def delete_user_preference(self, user_id, preference_key):
        return 1 if self.preferences.pop((user_id, preference_key), None) else 0


def test_capture_user_memory_persists_long_term_location_and_preference():
    repo = _FakeMemoryRepository()
    service = MemoryService(repository=repo)

    service.capture_user_memory(
        user_id="u1",
        session_id="s1",
        text="我在晋江市陈埭镇，后续优先推荐官方维修站，回答简洁一点",
    )

    assert repo.long_term[("u1", "profile.current_location")]["memory_value"] == "晋江市陈埭镇"
    assert repo.preferences[("u1", "reply.priority")]["memory_value"] == "官方维修站"
    assert repo.preferences[("u1", "reply.style")]["memory_value"] == "简洁"


def test_build_memory_system_messages_formats_persisted_memory():
    repo = _FakeMemoryRepository()
    service = MemoryService(repository=repo)
    repo.upsert_long_term_memory("u1", "profile.current_location", "晋江市陈埭镇")
    repo.upsert_user_preference("u1", "reply.style", "简洁")

    messages = service.build_memory_system_messages("u1")

    assert len(messages) == 1
    content = messages[0]["content"]
    assert "【长期记忆】" in content
    assert "profile.current_location (fact): 晋江市陈埭镇" in content
    assert "【用户偏好】" in content
    assert "reply.style (explicit): 简洁" in content


def test_service_query_location_can_be_inferred_without_prefix():
    repo = _FakeMemoryRepository()
    service = MemoryService(repository=repo)

    service.capture_user_memory(
        user_id="u1",
        session_id="s1",
        text="晋江市陈埭镇 电脑维修站",
    )

    assert repo.long_term[("u1", "profile.current_location")]["memory_value"] == "晋江市陈埭镇"


def test_capture_summary_memory_persists_summary_facts_and_preferences():
    repo = _FakeMemoryRepository()
    service = MemoryService(repository=repo)

    summary = ConversationSummary(
        summary_text="用户住在晋江市陈埭镇，希望优先推荐官方维修站。",
        entities=["ThinkPad T14"],
        preferences=["优先推荐官方维修站"],
        facts=["用户住在晋江市陈埭镇"],
        ongoing_issues=["电脑蓝屏"],
        decisions=["先查询附近官方维修站"],
    )

    service.capture_summary_memory("u1", "s1", summary)

    assert repo.long_term[("u1", "profile.summary_location")]["memory_value"] == "用户住在晋江市陈埭镇"
    assert repo.long_term[("u1", "entity.ThinkPad_T14")]["memory_value"] == "ThinkPad T14"
    assert repo.preferences[("u1", "summary.preference.优先推荐官方维修站")]["memory_value"] == "优先推荐官方维修站"
