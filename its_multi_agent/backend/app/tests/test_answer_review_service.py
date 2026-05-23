import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.answer_review import CandidateAnswer, EvidenceItem
from services.answer_review_service import answer_review_service


def test_review_returns_supported_when_evidence_matches_answer():
    verdict = answer_review_service.review_answer(
        candidate_answer=CandidateAnswer(answer="建议进入安全模式回退最近安装的驱动。"),
        evidence_items=[
            EvidenceItem(
                source="knowledge_base",
                snippet="进入安全模式后可回退最近安装的驱动，适合排查蓝屏问题。",
            )
        ],
    )

    assert verdict.status == "supported"
    assert verdict.should_downgrade is False


def test_review_returns_unsupported_when_evidence_does_not_support_answer():
    verdict = answer_review_service.review_answer(
        candidate_answer=CandidateAnswer(answer="必须更换主板才能解决。"),
        evidence_items=[
            EvidenceItem(
                source="knowledge_base",
                snippet="蓝屏常见原因包括驱动异常和系统文件损坏，可先做软件排查。",
            )
        ],
    )

    assert verdict.status == "unsupported"
    assert verdict.should_downgrade is True


def test_review_returns_conflicting_when_conflict_item_present():
    verdict = answer_review_service.review_answer(
        candidate_answer=CandidateAnswer(answer="可以直接升级 BIOS。"),
        evidence_items=[
            EvidenceItem(
                source="knowledge_base",
                snippet="升级 BIOS 前应先确认具体机型和版本。",
                support_level="supports",
            ),
            EvidenceItem(
                source="knowledge_base",
                snippet="未知机型时不要直接升级 BIOS，否则有风险。",
                support_level="conflicts",
            ),
        ],
    )

    assert verdict.status == "conflicting"
    assert verdict.should_downgrade is True


def test_review_returns_review_unavailable_without_evidence():
    verdict = answer_review_service.review_answer(
        candidate_answer=CandidateAnswer(answer="建议先备份数据。"),
        evidence_items=[],
    )

    assert verdict.status == "review_unavailable"
    assert verdict.should_downgrade is True
