import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.answer_review import CandidateAnswer, EvidenceItem, ReviewVerdict
from services.answer_postprocess_service import answer_postprocess_service


def test_supported_answer_is_preserved():
    candidate = CandidateAnswer(answer="建议先进入安全模式排查驱动。")
    verdict = ReviewVerdict(status="supported", summary="有证据支持。", should_downgrade=False)

    result = answer_postprocess_service.finalize(
        candidate_answer=candidate,
        review_verdict=verdict,
        evidence_items=[EvidenceItem(source="knowledge_base", snippet="安全模式可隔离驱动问题。")],
    )

    assert result.answer == "建议先进入安全模式排查驱动。"
    assert result.review_verdict.status == "supported"
    assert len(result.evidence_cards) == 1


def test_unsupported_answer_is_downgraded_with_uncertainty():
    candidate = CandidateAnswer(answer="必须更换主板。")
    verdict = ReviewVerdict(status="unsupported", summary="证据不足。", should_downgrade=True)

    result = answer_postprocess_service.finalize(
        candidate_answer=candidate,
        review_verdict=verdict,
        evidence_items=[EvidenceItem(source="knowledge_base", snippet="现有资料只提到驱动和系统排查。")],
    )

    assert "目前无法完全确认" in result.answer
    assert "现有证据" in result.answer
    assert result.review_verdict.status == "unsupported"


def test_conflicting_answer_is_downgraded_with_conflict_explanation():
    candidate = CandidateAnswer(answer="可以直接升级 BIOS。")
    verdict = ReviewVerdict(status="conflicting", summary="证据存在冲突。", should_downgrade=True)

    result = answer_postprocess_service.finalize(
        candidate_answer=candidate,
        review_verdict=verdict,
        evidence_items=[
            EvidenceItem(source="knowledge_base", snippet="升级 BIOS 前应确认机型。"),
            EvidenceItem(source="knowledge_base", snippet="未知机型时不要直接升级 BIOS。"),
        ],
    )

    assert "证据之间存在冲突" in result.answer
    assert result.review_verdict.status == "conflicting"
