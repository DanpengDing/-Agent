from typing import List

from schemas.agent_output import StructuredAgentOutput
from schemas.answer_review import CandidateAnswer, EvidenceCard, EvidenceItem, ReviewVerdict


class AnswerPostprocessService:
    def finalize(
        self,
        candidate_answer: CandidateAnswer,
        review_verdict: ReviewVerdict,
        evidence_items: List[EvidenceItem],
    ) -> StructuredAgentOutput:
        final_answer = candidate_answer.answer.strip()
        if review_verdict.status == "unsupported":
            final_answer = self._build_unsupported_answer(candidate_answer, evidence_items)
        elif review_verdict.status == "conflicting":
            final_answer = self._build_conflicting_answer(candidate_answer, evidence_items)
        elif review_verdict.status == "review_unavailable":
            final_answer = self._build_unavailable_answer(candidate_answer)

        return StructuredAgentOutput(
            intent=candidate_answer.intent,
            answer=final_answer,
            references=list(candidate_answer.references),
            next_action=candidate_answer.next_action,
            evidence_cards=self._build_evidence_cards(evidence_items),
            review_verdict=review_verdict,
        )

    @staticmethod
    def _build_unsupported_answer(candidate_answer: CandidateAnswer, evidence_items: List[EvidenceItem]) -> str:
        evidence_gap = evidence_items[0].snippet if evidence_items else "暂时没有可核验的资料"
        return (
            f"目前无法完全确认。{candidate_answer.answer} 这一结论还缺少直接支持，"
            f"现有证据更接近表明：{evidence_gap}"
        ).strip()

    @staticmethod
    def _build_conflicting_answer(candidate_answer: CandidateAnswer, evidence_items: List[EvidenceItem]) -> str:
        evidence_gap = evidence_items[0].snippet if evidence_items else "不同来源给出的信息不一致"
        return (
            f"目前无法完全确认，证据之间存在冲突。{candidate_answer.answer} 这一说法还需要进一步核实，"
            f"当前可见的信息包括：{evidence_gap}"
        ).strip()

    @staticmethod
    def _build_unavailable_answer(candidate_answer: CandidateAnswer) -> str:
        return (
            f"目前无法完全确认。{candidate_answer.answer} 这条回答暂时缺少可核验的检索证据，"
            "建议结合更多上下文或补充资料后再确认。"
        ).strip()

    @staticmethod
    def _build_evidence_cards(evidence_items: List[EvidenceItem]) -> List[EvidenceCard]:
        cards = []
        for item in evidence_items[:3]:
            cards.append(
                EvidenceCard(
                    title=item.title or item.source,
                    snippet=item.snippet,
                    source=item.source,
                    uri=item.uri,
                )
            )
        return cards


answer_postprocess_service = AnswerPostprocessService()
