import re
from typing import List

from schemas.answer_review import CandidateAnswer, EvidenceItem, RiskClassification


class RiskClassificationService:
    HIGH_RISK_QUERY_PATTERNS = [
        r"blue screen",
        r"bios",
        r"driver",
        r"repair station",
        r"address",
        r"navigation",
        r"what should i do",
        r"蓝屏",
        r"主板",
        r"维修站",
        r"地址",
        r"导航",
        r"怎么办",
    ]
    HIGH_RISK_ANSWER_PATTERNS = [
        r"must",
        r"immediately",
        r"replace",
        r"motherboard",
        r"bios",
        r"driver",
        r"wipe",
        r"format",
        r"必须",
        r"立即",
        r"更换",
        r"主板",
        r"刷bios",
        r"升级bios",
    ]

    def classify(
        self,
        query: str,
        candidate_answer: CandidateAnswer,
        evidence_items: List[EvidenceItem],
    ) -> RiskClassification:
        reasons = []
        combined_references = {item.lower() for item in candidate_answer.references}
        evidence_sources = {item.source.lower() for item in evidence_items if item.source}
        query_text = (query or "").lower()
        answer_text = (candidate_answer.answer or "").lower()

        if "knowledge_base" in combined_references or "knowledge_base" in evidence_sources:
            reasons.append("knowledge_base_reference")
        if any(re.search(pattern, query_text, flags=re.IGNORECASE) for pattern in self.HIGH_RISK_QUERY_PATTERNS):
            reasons.append("high_risk_query_pattern")
        if any(re.search(pattern, answer_text, flags=re.IGNORECASE) for pattern in self.HIGH_RISK_ANSWER_PATTERNS):
            reasons.append("high_risk_answer_pattern")
        if evidence_items:
            reasons.append("has_retrieval_evidence")

        if "knowledge_base_reference" in reasons or "high_risk_answer_pattern" in reasons:
            return RiskClassification(level="high", reasons=reasons, should_review=True)
        if "high_risk_query_pattern" in reasons and evidence_items:
            return RiskClassification(level="medium", reasons=reasons, should_review=True)
        return RiskClassification(level="low", reasons=reasons, should_review=False)


risk_classification_service = RiskClassificationService()
