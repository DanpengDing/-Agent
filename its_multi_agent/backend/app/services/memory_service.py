from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from schemas.session_memory import ConversationSummary

from infrastructure.logging.logger import logger
from repositories.memory_repository import memory_repository


@dataclass
class ExtractedMemoryItem:
    key: str
    value: str
    confidence: float = 0.80


class MemoryService:
    """三层记忆中的长期记忆与用户偏好服务。"""

    LOCATION_QUERY_NOISE_PATTERNS = [
        r"最近的?",
        r"离我最近",
        r"附近",
        r"我要去",
        r"我想去",
        r"帮我找",
        r"导航去",
        r"电脑维修站",
        r"维修站",
        r"电脑维修",
        r"修电脑",
    ]

    LONG_TERM_PATTERNS = [
        (re.compile(r"(?:我在|我住在|我目前在|人在)([\u4e00-\u9fa5A-Za-z0-9·\-]{2,40})"), "profile.current_location", 0.95),
        (re.compile(r"(?:我的电脑是|我电脑是|电脑是)([\u4e00-\u9fa5A-Za-z0-9\-\s]{2,50})"), "device.model", 0.90),
        (re.compile(r"(?:我是|我用的是)(联想|ThinkPad|华为|华硕|戴尔|惠普|苹果|MacBook)"), "device.brand", 0.90),
    ]

    PREFERENCE_PATTERNS = [
        (re.compile(r"(?:以后|后续|下次)?(?:请|希望)?(?:优先|首先)(?:推荐|考虑|查询)?(.{2,30})"), "reply.priority", 0.90),
        (re.compile(r"(?:回答|说明|回复)(?:尽量)?(简洁|详细|一步一步|直接一点)"), "reply.style", 0.88),
        (re.compile(r"(?:不要|别)(.{2,30})"), "reply.avoid", 0.82),
        (re.compile(r"(?:我更喜欢|我喜欢)(.{2,30})"), "user.like", 0.85),
    ]

    LOCATION_SUFFIX_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,20}(?:省|市|区|县|镇|乡|街道|村))")

    def __init__(self, repository=memory_repository):
        self._repo = repository

    def capture_user_memory(self, user_id: str, session_id: str, text: str) -> None:
        if not user_id or not text:
            return

        try:
            for item in self._extract_long_term_memories(text):
                self._repo.upsert_long_term_memory(
                    user_id=user_id,
                    memory_key=item.key,
                    memory_value=item.value,
                    memory_type="fact",
                    topic=self._infer_topic(item.key, text),
                    confidence=item.confidence,
                    source_session_id=session_id,
                    source_text=text,
                )

            for item in self._extract_user_preferences(text):
                self._repo.upsert_user_preference(
                    user_id=user_id,
                    preference_key=item.key,
                    preference_value=item.value,
                    preference_type="explicit",
                    confidence=item.confidence,
                    source_session_id=session_id,
                    source_text=text,
                )
        except Exception as exc:
            logger.warning("[MemoryService] capture user memory skipped user=%s error=%s", user_id, exc)

    def capture_summary_memory(
        self,
        user_id: str,
        session_id: str,
        summary: Optional[ConversationSummary],
    ) -> None:
        if not user_id or summary is None:
            return

        summary_text = summary.summary_text or ""
        try:
            for fact in summary.facts[:5]:
                memory_key = self._infer_memory_key_from_fact(fact)
                self._repo.upsert_long_term_memory(
                    user_id=user_id,
                    memory_key=memory_key,
                    memory_value=fact,
                    memory_type="summary_fact",
                    topic=self._infer_topic(memory_key, fact),
                    confidence=0.72,
                    source_session_id=session_id,
                    source_text=summary_text,
                )

            for entity in summary.entities[:5]:
                self._repo.upsert_long_term_memory(
                    user_id=user_id,
                    memory_key=f"entity.{self._slugify(entity)}",
                    memory_value=entity,
                    memory_type="entity",
                    topic=self._infer_topic("entity", entity),
                    confidence=0.68,
                    source_session_id=session_id,
                    source_text=summary_text,
                )

            for issue in summary.ongoing_issues[:5]:
                self._repo.upsert_long_term_memory(
                    user_id=user_id,
                    memory_key=f"issue.ongoing.{self._slugify(issue)}",
                    memory_value=issue,
                    memory_type="ongoing_issue",
                    topic=self._infer_topic("issue", issue),
                    confidence=0.66,
                    source_session_id=session_id,
                    source_text=summary_text,
                )

            for decision in summary.decisions[:5]:
                self._repo.upsert_long_term_memory(
                    user_id=user_id,
                    memory_key=f"decision.{self._slugify(decision)}",
                    memory_value=decision,
                    memory_type="decision",
                    topic=self._infer_topic("decision", decision),
                    confidence=0.70,
                    source_session_id=session_id,
                    source_text=summary_text,
                )

            for preference in summary.preferences[:5]:
                self._repo.upsert_user_preference(
                    user_id=user_id,
                    preference_key=f"summary.preference.{self._slugify(preference)}",
                    preference_value=preference,
                    preference_type="summary_inferred",
                    confidence=0.65,
                    source_session_id=session_id,
                    source_text=summary_text,
                )
        except Exception as exc:
            logger.warning("[MemoryService] capture summary memory skipped user=%s error=%s", user_id, exc)

    def list_long_term_memories(self, user_id: str, limit: int = 20) -> List[Dict[str, str]]:
        return self._repo.list_long_term_memories(user_id, limit=limit)

    def list_user_preferences(self, user_id: str, limit: int = 20) -> List[Dict[str, str]]:
        return self._repo.list_user_preferences(user_id, limit=limit)

    def set_user_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: str,
        session_id: str = "",
        preference_type: str = "manual",
    ) -> None:
        self._repo.upsert_user_preference(
            user_id=user_id,
            preference_key=preference_key,
            preference_value=preference_value,
            preference_type=preference_type,
            confidence=1.0,
            source_session_id=session_id,
            source_text=preference_value,
        )

    def delete_user_preference(self, user_id: str, preference_key: str) -> int:
        return self._repo.delete_user_preference(user_id, preference_key)

    def build_memory_system_messages(self, user_id: str) -> List[Dict[str, str]]:
        if not user_id:
            return []

        try:
            long_term_memories = self._repo.list_long_term_memories(user_id, limit=10)
            user_preferences = self._repo.list_user_preferences(user_id, limit=10)
        except Exception as exc:
            logger.warning("[MemoryService] load memory context skipped user=%s error=%s", user_id, exc)
            return []

        sections: List[str] = []
        if long_term_memories:
            lines = ["【长期记忆】"]
            for item in long_term_memories:
                lines.append(f"- {item['memory_key']} ({item.get('memory_type', 'fact')}): {item['memory_value']}")
            sections.append("\n".join(lines))

        if user_preferences:
            lines = ["【用户偏好】"]
            for item in user_preferences:
                lines.append(f"- {item['memory_key']} ({item.get('memory_type', 'explicit')}): {item['memory_value']}")
            sections.append("\n".join(lines))

        if not sections:
            return []

        sections.append("如果这些记忆与用户本轮明确表达冲突，以用户本轮最新表述为准。")
        return [{"role": "system", "content": "\n\n".join(sections)}]

    def _extract_long_term_memories(self, text: str) -> List[ExtractedMemoryItem]:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return []

        items: List[ExtractedMemoryItem] = []
        for pattern, memory_key, confidence in self.LONG_TERM_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                items.append(ExtractedMemoryItem(memory_key, self._clean_value(match.group(1)), confidence))

        inferred_location = self._extract_location_from_service_query(normalized_text)
        if inferred_location:
            items.append(ExtractedMemoryItem("profile.current_location", inferred_location, 0.86))

        return self._dedupe_items(items)

    def _extract_user_preferences(self, text: str) -> List[ExtractedMemoryItem]:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return []

        items: List[ExtractedMemoryItem] = []
        for pattern, preference_key, confidence in self.PREFERENCE_PATTERNS:
            match = pattern.search(normalized_text)
            if match:
                items.append(ExtractedMemoryItem(preference_key, self._clean_value(match.group(1)), confidence))
        return self._dedupe_items(items)

    def _extract_location_from_service_query(self, text: str) -> Optional[str]:
        normalized = text
        for pattern in self.LOCATION_QUERY_NOISE_PATTERNS:
            normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" ，,。；;、")
        if not normalized:
            return None

        matches = self.LOCATION_SUFFIX_PATTERN.findall(normalized)
        if matches:
            return "".join(matches)
        return None

    @staticmethod
    def _clean_value(value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" ，,。；;、")
        text = re.split(r"[，,。；;、\n]", text, maxsplit=1)[0].strip()
        return text

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", value or "").strip("_")
        return normalized[:48] or "item"

    @staticmethod
    def _infer_memory_key_from_fact(fact: str) -> str:
        if any(token in fact for token in ["住在", "位于", "在", "城市", "区", "镇"]):
            return "profile.summary_location"
        if any(token in fact.lower() for token in ["thinkpad", "macbook"]) or any(token in fact for token in ["联想", "华为", "戴尔", "苹果"]):
            return "device.summary"
        return f"fact.{MemoryService._slugify(fact)}"

    @staticmethod
    def _infer_topic(key: str, value: str) -> str:
        text = f"{key} {value}".lower()
        if any(token in text for token in ["维修", "repair", "服务站"]):
            return "repair"
        if any(token in text for token in ["电脑", "蓝屏", "device", "thinkpad", "macbook"]):
            return "device"
        if any(token in text for token in ["location", "城市", "区", "镇"]):
            return "location"
        if any(token in text for token in ["回答", "reply", "风格", "优先"]):
            return "preference"
        return "general"

    @staticmethod
    def _dedupe_items(items: List[ExtractedMemoryItem]) -> List[ExtractedMemoryItem]:
        deduped: Dict[str, ExtractedMemoryItem] = {}
        for item in items:
            if not item.value:
                continue
            existing = deduped.get(item.key)
            if existing is None or item.confidence >= existing.confidence:
                deduped[item.key] = item
        return list(deduped.values())


memory_service = MemoryService()
