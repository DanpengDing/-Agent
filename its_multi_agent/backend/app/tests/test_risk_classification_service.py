import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.answer_review import CandidateAnswer, EvidenceItem
from services.risk_classification_service import risk_classification_service


def test_classify_marks_knowledge_backed_answer_high_risk():
    candidate = CandidateAnswer(
        answer="Enter safe mode and uninstall the newest driver.",
        references=["knowledge_base"],
    )
    evidence = [EvidenceItem(source="knowledge_base", snippet="Safe mode can isolate recent driver issues.")]

    classification = risk_classification_service.classify(
        query="What should I do about a blue screen?",
        candidate_answer=candidate,
        evidence_items=evidence,
    )

    assert classification.level == "high"
    assert "knowledge_base_reference" in classification.reasons


def test_classify_marks_general_reply_low_risk():
    candidate = CandidateAnswer(answer="Hi, I can help analyze the issue.")

    classification = risk_classification_service.classify(
        query="hello",
        candidate_answer=candidate,
        evidence_items=[],
    )

    assert classification.level == "low"
    assert classification.should_review is False


def test_classify_marks_high_risk_candidate_conclusion_without_kb_markers():
    candidate = CandidateAnswer(answer="You must replace the motherboard and upgrade BIOS immediately.")

    classification = risk_classification_service.classify(
        query="What should I do?",
        candidate_answer=candidate,
        evidence_items=[],
    )

    assert classification.should_review is True
    assert "high_risk_answer_pattern" in classification.reasons
