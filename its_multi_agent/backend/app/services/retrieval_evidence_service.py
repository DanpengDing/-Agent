import ast
import json
from typing import Any, Dict, List

from schemas.answer_review import EvidenceItem


class RetrievalEvidenceService:
    COLLECTION_KEYS = ("items", "results", "data", "documents", "chunks", "records")

    def normalize(self, payload: Any) -> List[EvidenceItem]:
        parsed = self._parse_payload(payload)
        if parsed is None:
            return []
        if isinstance(parsed, list):
            return [item for item in (self._build_evidence_item(row) for row in parsed) if item is not None]
        if isinstance(parsed, dict):
            for key in self.COLLECTION_KEYS:
                if isinstance(parsed.get(key), list):
                    return self.normalize(parsed[key])
            item = self._build_evidence_item(parsed)
            return [item] if item is not None else []
        if isinstance(parsed, str) and parsed.strip():
            return [EvidenceItem(source="retrieval", snippet=parsed.strip())]
        return []

    def normalize_task_payload(self, task: Dict[str, Any] | None) -> List[EvidenceItem]:
        if not task:
            return []

        last_result = task.get("last_tool_result_json") or {}
        if not isinstance(last_result, dict):
            return []

        direct_evidence = last_result.get("evidence_items")
        if isinstance(direct_evidence, list):
            evidence = self.normalize(direct_evidence)
            if evidence:
                return evidence

        payload = last_result.get("payload")
        if payload is not None:
            parsed_payload = self._parse_payload(payload)
            if isinstance(parsed_payload, dict) and isinstance(parsed_payload.get("evidence_items"), list):
                evidence = self.normalize(parsed_payload.get("evidence_items"))
                if evidence:
                    return evidence
            evidence = self.normalize(parsed_payload)
            if evidence:
                return evidence

        preview = last_result.get("output_preview")
        if preview:
            parsed_preview = self._parse_payload(preview)
            if isinstance(parsed_preview, dict) and isinstance(parsed_preview.get("evidence_items"), list):
                evidence = self.normalize(parsed_preview.get("evidence_items"))
                if evidence:
                    return evidence
            return self.normalize(parsed_preview)

        return []

    @staticmethod
    def _parse_payload(payload: Any):
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                try:
                    return ast.literal_eval(text)
                except Exception:
                    return text
        return payload

    def _build_evidence_item(self, row: Any) -> EvidenceItem | None:
        if isinstance(row, EvidenceItem):
            return row
        if isinstance(row, str):
            text = row.strip()
            if not text:
                return None
            return EvidenceItem(source="retrieval", snippet=text)
        if not isinstance(row, dict):
            return None

        title = row.get("title") or row.get("service_station_name") or row.get("name")
        snippet = (
            row.get("snippet")
            or row.get("content")
            or row.get("summary")
            or self._compose_fallback_snippet(row)
        )
        if not snippet:
            return None

        support_level = row.get("support_level")
        if support_level not in {"supports", "neutral", "conflicts"}:
            support_level = "neutral"

        metadata = dict(row)
        return EvidenceItem(
            source=row.get("source") or "retrieval",
            title=title,
            snippet=str(snippet).strip(),
            uri=row.get("uri") or row.get("url") or row.get("link"),
            support_level=support_level,
            metadata=metadata,
        )

    @staticmethod
    def _compose_fallback_snippet(row: Dict[str, Any]) -> str:
        parts = []
        if row.get("address"):
            parts.append(str(row["address"]))
        if row.get("phone"):
            parts.append(f"Phone: {row['phone']}")
        if row.get("distance_km") is not None:
            parts.append(f"Distance about {row['distance_km']} km")
        return " | ".join(parts)


retrieval_evidence_service = RetrievalEvidenceService()
