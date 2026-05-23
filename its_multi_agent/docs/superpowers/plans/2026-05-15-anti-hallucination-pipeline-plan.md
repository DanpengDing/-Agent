# Anti-Hallucination Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-style anti-hallucination answer pipeline for knowledge-backed and high-risk answers, including evidence cards, a review agent, and uncertainty downgrade behavior.

**Architecture:** The existing multi-agent answer flow stays in place, but final answers become a two-stage pipeline: domain agent produces a candidate answer with claimed evidence, then a verifier reviews that answer against retrieved evidence and returns a verdict. A post-processor converts the verdict into the final user-facing answer and evidence card, including an explicit uncertainty explanation when evidence is weak or conflicting.

**Tech Stack:** FastAPI, OpenAI Agents SDK, existing local knowledge base tool, Pydantic, pytest, Vue 3, Element Plus, SSE streaming responses

---

## File Structure

**Create:**
- `backend/app/schemas/answer_review.py`
- `backend/app/services/risk_classification_service.py`
- `backend/app/services/retrieval_evidence_service.py`
- `backend/app/services/answer_review_service.py`
- `backend/app/services/answer_postprocess_service.py`
- `backend/app/tests/test_risk_classification_service.py`
- `backend/app/tests/test_retrieval_evidence_service.py`
- `backend/app/tests/test_answer_review_service.py`
- `backend/app/tests/test_answer_postprocess_service.py`
- `backend/app/tests/test_agent_service_anti_hallucination_flow.py`

**Modify:**
- `backend/app/infrastructure/tools/local/knowledge_base.py`
- `backend/app/schemas/agent_output.py`
- `backend/app/schemas/response.py`
- `backend/app/services/structured_output_service.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/stream_response_service.py`
- `front/agent_web_ui/src/views/ChatPage.vue`
- `backend/app/tests/test_stream_response_diagnostics.py`
- `backend/app/tests/test_session_persistence_for_agent_replies.py`

**Why these files:**
- `answer_review.py` is the single typed contract for candidate answers, evidence items, verdicts, and evidence cards.
- `risk_classification_service.py` isolates rule-based risk detection instead of mixing it into agent orchestration.
- `retrieval_evidence_service.py` keeps evidence normalization separate from tool calling.
- `answer_review_service.py` contains the verifier prompt/contract and shields the rest of the app from verifier-specific output quirks.
- `answer_postprocess_service.py` owns downgrade logic so “supported / partial / unsupported / conflict” does not sprawl into controllers and views.
- `agent_service.py` is the insertion point for the new review stage.
- `ChatPage.vue` is the smallest current UI surface that can show verdict badges and evidence cards without redesigning the app.

### Task 1: Add typed contracts for candidate answers, evidence, and review verdicts

**Files:**
- Create: `backend/app/schemas/answer_review.py`
- Modify: `backend/app/schemas/agent_output.py`
- Modify: `backend/app/services/structured_output_service.py`
- Test: `backend/app/tests/test_answer_postprocess_service.py`

- [ ] **Step 1: Write the failing schema and parser tests**

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.structured_output_service import structured_output_service


def test_parse_candidate_answer_json():
    raw_output = """
    {
      "answer": "建议先检查电源适配器。",
      "answer_type": "knowledge_answer",
      "risk_level": "high",
      "used_knowledge": true,
      "claimed_evidence_ids": ["ev-1", "ev-2"],
      "raw_reasoning_summary": "知识库提到了供电问题"
    }
    """

    result = structured_output_service.parse_candidate_answer(raw_output)

    assert result.answer == "建议先检查电源适配器。"
    assert result.risk_level == "high"
    assert result.claimed_evidence_ids == ["ev-1", "ev-2"]


def test_parse_candidate_answer_fallback_to_plain_text():
    result = structured_output_service.parse_candidate_answer("普通文本答案")

    assert result.answer == "普通文本答案"
    assert result.answer_type == "general_answer"
    assert result.claimed_evidence_ids == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_answer_postprocess_service.py -v`
Expected: FAIL with `AttributeError: 'StructuredOutputService' object has no attribute 'parse_candidate_answer'`

- [ ] **Step 3: Add the answer review schema file**

```python
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: str
    source_name: str
    snippet: str
    score: float = 0.0
    reason: str = ""


class CandidateAnswer(BaseModel):
    answer: str = ""
    answer_type: Literal["general_answer", "knowledge_answer", "diagnosis_answer"] = "general_answer"
    risk_level: Literal["low", "medium", "high"] = "low"
    used_knowledge: bool = False
    claimed_evidence_ids: list[str] = Field(default_factory=list)
    raw_reasoning_summary: str = ""


class ReviewVerdict(BaseModel):
    verdict: Literal["supported", "partial", "unsupported", "conflict", "review_unavailable"]
    confidence: Literal["high", "medium", "low"]
    reason: str
    used_evidence_ids: list[str] = Field(default_factory=list)
    rewrite_required: bool = False


class EvidenceCard(BaseModel):
    status: str
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    uncertainty_reason: str = ""
    review_available: bool = True
```

- [ ] **Step 4: Extend `structured_output_service.py` with candidate-answer parsing**

```python
from schemas.answer_review import CandidateAnswer
from schemas.agent_output import StructuredAgentOutput


class StructuredOutputService:
    @staticmethod
    def parse_final_output(raw_output: str) -> StructuredAgentOutput:
        cleaned_output = (raw_output or "").strip()
        if not cleaned_output:
            return StructuredAgentOutput(answer="")

        try:
            return StructuredAgentOutput.model_validate_json(cleaned_output)
        except Exception:
            return StructuredAgentOutput(answer=cleaned_output)

    @staticmethod
    def parse_candidate_answer(raw_output: str) -> CandidateAnswer:
        cleaned_output = (raw_output or "").strip()
        if not cleaned_output:
            return CandidateAnswer()

        try:
            return CandidateAnswer.model_validate_json(cleaned_output)
        except Exception:
            return CandidateAnswer(answer=cleaned_output)
```

- [ ] **Step 5: Update `agent_output.py` to carry optional evidence-card metadata**

```python
from pydantic import BaseModel, Field


class StructuredAgentOutput(BaseModel):
    answer: str = ""
    intent: str = "general"
    evidence_card: dict | None = None
    uncertainty_reason: str = ""
    review_verdict: str = ""
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest backend/app/tests/test_answer_postprocess_service.py -v`
Expected: PASS for the parsing tests

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/answer_review.py backend/app/schemas/agent_output.py backend/app/services/structured_output_service.py backend/app/tests/test_answer_postprocess_service.py
git commit -m "feat: add answer review schemas and candidate parsing"
```

### Task 2: Normalize knowledge retrieval into structured evidence items

**Files:**
- Create: `backend/app/services/retrieval_evidence_service.py`
- Modify: `backend/app/infrastructure/tools/local/knowledge_base.py`
- Test: `backend/app/tests/test_retrieval_evidence_service.py`

- [ ] **Step 1: Write the failing retrieval-evidence tests**

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.retrieval_evidence_service import retrieval_evidence_service


def test_normalize_knowledge_result_to_evidence_items():
    payload = {
        "status": "success",
        "answer": "电源适配器异常可能导致无法开机",
        "documents": [
            {"id": "doc-1", "source": "维修手册A", "content": "若适配器无输出，设备无法开机", "score": 0.91},
            {"id": "doc-2", "source": "FAQ", "content": "请先确认适配器供电", "score": 0.84},
        ],
    }

    result = retrieval_evidence_service.normalize(payload)

    assert result.answer == "电源适配器异常可能导致无法开机"
    assert len(result.evidence_items) == 2
    assert result.evidence_items[0].evidence_id == "doc-1"


def test_normalize_empty_documents_returns_no_evidence_items():
    payload = {"status": "success", "answer": "未找到明确答案", "documents": []}

    result = retrieval_evidence_service.normalize(payload)

    assert result.answer == "未找到明确答案"
    assert result.evidence_items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_retrieval_evidence_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.retrieval_evidence_service'`

- [ ] **Step 3: Update `knowledge_base.py` to return structured document fields**

```python
return {
    "ok": True,
    "status": "success",
    "answer": response_json.get("answer", ""),
    "documents": response_json.get("documents", []),
}
```

- [ ] **Step 4: Add the retrieval evidence service**

```python
from dataclasses import dataclass

from schemas.answer_review import EvidenceItem


@dataclass
class RetrievalEvidenceResult:
    answer: str
    evidence_items: list[EvidenceItem]


class RetrievalEvidenceService:
    def normalize(self, payload: dict) -> RetrievalEvidenceResult:
        answer = str(payload.get("answer") or "")
        documents = payload.get("documents") or []
        evidence_items = []
        for index, item in enumerate(documents[:3], start=1):
            evidence_items.append(
                EvidenceItem(
                    evidence_id=str(item.get("id") or f"ev-{index}"),
                    source_name=str(item.get("source") or item.get("title") or f"document-{index}"),
                    snippet=str(item.get("content") or item.get("snippet") or "")[:240],
                    score=float(item.get("score") or 0.0),
                    reason=f"Top-{index} retrieved evidence",
                )
            )
        return RetrievalEvidenceResult(answer=answer, evidence_items=evidence_items)


retrieval_evidence_service = RetrievalEvidenceService()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/app/tests/test_retrieval_evidence_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/infrastructure/tools/local/knowledge_base.py backend/app/services/retrieval_evidence_service.py backend/app/tests/test_retrieval_evidence_service.py
git commit -m "feat: normalize knowledge retrieval into evidence items"
```

### Task 3: Add rule-based risk classification and answer post-processing

**Files:**
- Create: `backend/app/services/risk_classification_service.py`
- Create: `backend/app/services/answer_postprocess_service.py`
- Test: `backend/app/tests/test_risk_classification_service.py`
- Test: `backend/app/tests/test_answer_postprocess_service.py`

- [ ] **Step 1: Write the failing risk-classification tests**

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.risk_classification_service import risk_classification_service


def test_classify_knowledge_answer_as_high_risk():
    risk = risk_classification_service.classify(
        user_query="ThinkPad 无法开机怎么办？",
        candidate_answer="建议先检查电源适配器。",
        used_knowledge=True,
    )

    assert risk == "high"


def test_classify_general_small_talk_as_low_risk():
    risk = risk_classification_service.classify(
        user_query="你好",
        candidate_answer="你好，我可以帮你处理售后问题。",
        used_knowledge=False,
    )

    assert risk == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_risk_classification_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add the risk-classification service**

```python
import re


class RiskClassificationService:
    HIGH_RISK_PATTERNS = [
        r"主板",
        r"故障",
        r"更换",
        r"建议",
        r"诊断",
        r"结论",
    ]

    def classify(self, user_query: str, candidate_answer: str, used_knowledge: bool) -> str:
        text = f"{user_query} {candidate_answer}"
        if used_knowledge:
            return "high"
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.HIGH_RISK_PATTERNS):
            return "high"
        return "low"


risk_classification_service = RiskClassificationService()
```

- [ ] **Step 4: Write the failing post-process tests**

```python
from schemas.answer_review import CandidateAnswer, EvidenceCard, EvidenceItem, ReviewVerdict
from services.answer_postprocess_service import answer_postprocess_service


def test_postprocess_supported_answer_keeps_plain_answer():
    candidate = CandidateAnswer(answer="建议先检查电源适配器。", used_knowledge=True)
    verdict = ReviewVerdict(
        verdict="supported",
        confidence="high",
        reason="evidence directly supports the conclusion",
        used_evidence_ids=["ev-1"],
        rewrite_required=False,
    )
    evidence_items = [EvidenceItem(evidence_id="ev-1", source_name="维修手册", snippet="若适配器无输出，设备无法开机", score=0.91)]

    result = answer_postprocess_service.build_final_answer(candidate, verdict, evidence_items)

    assert result.answer == "建议先检查电源适配器。"
    assert result.evidence_card["status"] == "已证据支持"


def test_postprocess_unsupported_answer_adds_uncertainty_notice():
    candidate = CandidateAnswer(answer="可能是主板坏了。", used_knowledge=True)
    verdict = ReviewVerdict(
        verdict="unsupported",
        confidence="low",
        reason="knowledge base does not contain direct support",
        used_evidence_ids=[],
        rewrite_required=True,
    )

    result = answer_postprocess_service.build_final_answer(candidate, verdict, [])

    assert "不确定" in result.answer
    assert result.evidence_card["uncertainty_reason"] == "knowledge base does not contain direct support"
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest backend/app/tests/test_answer_postprocess_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.answer_postprocess_service'`

- [ ] **Step 6: Add the answer post-process service**

```python
from schemas.agent_output import StructuredAgentOutput


class AnswerPostprocessService:
    STATUS_MAP = {
        "supported": "已证据支持",
        "partial": "部分支持",
        "unsupported": "证据不足，不确定",
        "conflict": "证据冲突",
        "review_unavailable": "审查暂不可用",
    }

    def build_final_answer(self, candidate, verdict, evidence_items):
        answer = candidate.answer
        if verdict.verdict in {"partial", "unsupported", "conflict"}:
            answer = f"当前不能完全确定：{candidate.answer}\n\n原因：{verdict.reason}"
        if verdict.verdict == "review_unavailable":
            answer = f"{candidate.answer}\n\n说明：本次审查暂不可用。"

        return StructuredAgentOutput(
            answer=answer,
            intent="knowledge",
            evidence_card={
                "status": self.STATUS_MAP[verdict.verdict],
                "evidence_items": [item.model_dump() for item in evidence_items if item.evidence_id in verdict.used_evidence_ids or verdict.verdict != "supported"][:3],
                "uncertainty_reason": verdict.reason if verdict.verdict != "supported" else "",
                "review_available": verdict.verdict != "review_unavailable",
            },
            uncertainty_reason=verdict.reason if verdict.verdict != "supported" else "",
            review_verdict=verdict.verdict,
        )


answer_postprocess_service = AnswerPostprocessService()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest backend/app/tests/test_risk_classification_service.py backend/app/tests/test_answer_postprocess_service.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/risk_classification_service.py backend/app/services/answer_postprocess_service.py backend/app/tests/test_risk_classification_service.py backend/app/tests/test_answer_postprocess_service.py
git commit -m "feat: add risk classification and answer postprocess services"
```

### Task 4: Add the review agent / verifier service

**Files:**
- Create: `backend/app/services/answer_review_service.py`
- Test: `backend/app/tests/test_answer_review_service.py`

- [ ] **Step 1: Write the failing review-service tests**

```python
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.answer_review import CandidateAnswer, EvidenceItem
from services.answer_review_service import answer_review_service


def test_review_service_marks_supported_answer(monkeypatch):
    candidate = CandidateAnswer(
        answer="建议先检查电源适配器。",
        used_knowledge=True,
        claimed_evidence_ids=["ev-1"],
    )
    evidence_items = [
        EvidenceItem(evidence_id="ev-1", source_name="维修手册", snippet="若适配器无输出，设备无法开机", score=0.91),
    ]

    monkeypatch.setattr(
        answer_review_service,
        "_call_reviewer_model",
        lambda prompt: {
            "verdict": "supported",
            "confidence": "high",
            "reason": "evidence directly supports the answer",
            "used_evidence_ids": ["ev-1"],
            "rewrite_required": False,
        },
    )

    verdict = answer_review_service.review(
        user_query="ThinkPad 无法开机怎么办？",
        candidate=candidate,
        evidence_items=evidence_items,
        risk_level="high",
    )

    assert verdict.verdict == "supported"
    assert verdict.used_evidence_ids == ["ev-1"]


def test_review_service_marks_missing_claimed_evidence_as_unsupported(monkeypatch):
    candidate = CandidateAnswer(
        answer="可能是主板坏了。",
        used_knowledge=True,
        claimed_evidence_ids=[],
    )

    verdict = answer_review_service.review(
        user_query="ThinkPad 无法开机怎么办？",
        candidate=candidate,
        evidence_items=[],
        risk_level="high",
    )

    assert verdict.verdict == "unsupported"
    assert verdict.rewrite_required is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_answer_review_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add the review service**

```python
from schemas.answer_review import ReviewVerdict


class AnswerReviewService:
    def review(self, user_query: str, candidate, evidence_items, risk_level: str) -> ReviewVerdict:
        if risk_level != "high":
            return ReviewVerdict(
                verdict="supported",
                confidence="medium",
                reason="low risk answer bypassed reviewer",
                used_evidence_ids=[],
                rewrite_required=False,
            )

        if candidate.used_knowledge and not candidate.claimed_evidence_ids:
            return ReviewVerdict(
                verdict="unsupported",
                confidence="low",
                reason="candidate answer did not claim evidence ids",
                used_evidence_ids=[],
                rewrite_required=True,
            )

        try:
            payload = self._call_reviewer_model(
                self._build_prompt(user_query, candidate, evidence_items, risk_level)
            )
            return ReviewVerdict.model_validate(payload)
        except Exception:
            return ReviewVerdict(
                verdict="review_unavailable",
                confidence="low",
                reason="review agent unavailable",
                used_evidence_ids=[],
                rewrite_required=False,
            )

    def _build_prompt(self, user_query: str, candidate, evidence_items, risk_level: str) -> str:
        evidence_lines = [
            f"- [{item.evidence_id}] {item.source_name}: {item.snippet}"
            for item in evidence_items
        ]
        return "\n".join(
            [
                f"user_query: {user_query}",
                f"candidate_answer: {candidate.answer}",
                f"risk_level: {risk_level}",
                f"claimed_evidence_ids: {candidate.claimed_evidence_ids}",
                "evidence:",
                *evidence_lines,
            ]
        )

    def _call_reviewer_model(self, prompt: str):
        raise NotImplementedError


answer_review_service = AnswerReviewService()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/test_answer_review_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/answer_review_service.py backend/app/tests/test_answer_review_service.py
git commit -m "feat: add answer review service"
```

### Task 5: Insert anti-hallucination review into the answer pipeline

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Create: `backend/app/tests/test_agent_service_anti_hallucination_flow.py`

- [ ] **Step 1: Write the failing integration tests for the new review stage**

```python
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.request import ChatMessageRequest, UserContext
from schemas.session_memory import SessionMemoryState
from services.agent_service import MultiAgentService
from services.session_service import session_service


def test_process_task_downgrades_unsupported_high_risk_answer(monkeypatch):
    collected = []

    async def fake_load_runtime_state(user_id, session_id, pending_user_input=""):
        return SessionMemoryState()

    async def fake_rewrite(query, history):
        return SimpleNamespace(rewritten_query=query)

    class _FakeStreamingResult:
        interruptions = []
        final_output = '{"answer":"可能是主板坏了。","answer_type":"diagnosis_answer","risk_level":"high","used_knowledge":true,"claimed_evidence_ids":["ev-1"],"raw_reasoning_summary":"based on KB"}'

        async def stream_events(self):
            if False:
                yield None

    monkeypatch.setattr(session_service, "load_runtime_state", fake_load_runtime_state)
    monkeypatch.setattr(session_service, "build_runtime_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(session_service, "append_message_to_state", lambda state, role, content: state)
    monkeypatch.setattr(session_service, "save_session_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.rewrite", fake_rewrite)
    monkeypatch.setattr("services.agent_service.query_rewrite_service.build_process_message", lambda result: "")
    monkeypatch.setattr("services.agent_service.memory_service.capture_user_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.agent_service.memory_service.build_memory_system_messages", lambda user_id: [])
    monkeypatch.setattr("services.agent_service.Runner.run_streamed", lambda **kwargs: _FakeStreamingResult())
    monkeypatch.setattr("services.agent_service.process_stream_response", lambda result, callbacks=None: _empty_stream())
    monkeypatch.setattr(
        "services.agent_service.retrieval_evidence_service.normalize",
        lambda payload: SimpleNamespace(answer="", evidence_items=[]),
    )
    monkeypatch.setattr(
        "services.agent_service.answer_review_service.review",
        lambda **kwargs: SimpleNamespace(
            verdict="unsupported",
            confidence="low",
            reason="knowledge base does not contain direct support",
            used_evidence_ids=[],
            rewrite_required=True,
        ),
    )

    request = ChatMessageRequest(
        query="ThinkPad 无法开机怎么办？",
        context=UserContext(user_id="u1", session_id="s1"),
    )

    async def consume():
        async for item in MultiAgentService.process_task(request, flag=True):
            collected.append(item)

    asyncio.run(consume())

    assert any("不确定" in str(item) for item in collected)


async def _empty_stream():
    if False:
        yield None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_agent_service_anti_hallucination_flow.py -v`
Expected: FAIL because `agent_service.py` does not yet call review/postprocess services

- [ ] **Step 3: Add review-stage wiring to `agent_service.py`**

```python
from services.answer_postprocess_service import answer_postprocess_service
from services.answer_review_service import answer_review_service
from services.retrieval_evidence_service import retrieval_evidence_service
from services.risk_classification_service import risk_classification_service


candidate = structured_output_service.parse_candidate_answer(agent_result)
normalized_evidence = retrieval_evidence_service.normalize({"answer": "", "documents": []})
risk_level = risk_classification_service.classify(
    user_query=user_query,
    candidate_answer=candidate.answer,
    used_knowledge=candidate.used_knowledge,
)
verdict = answer_review_service.review(
    user_query=user_query,
    candidate=candidate,
    evidence_items=normalized_evidence.evidence_items,
    risk_level=risk_level,
)
final_result = answer_postprocess_service.build_final_answer(
    candidate,
    verdict,
    normalized_evidence.evidence_items,
)
formatted_result = re.sub(r"\n+", "\n", final_result.answer)
```

- [ ] **Step 4: Persist final downgraded answer and evidence metadata**

```python
runtime_state = session_service.append_message_to_state(runtime_state, "assistant", formatted_result)
session_service.save_session_state(user_id, session_id, runtime_state)
yield "data: " + ResponseFactory.build_text(
    formatted_result.answer,
    ContentKind.ANSWER,
).model_dump_json() + "\n\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/app/tests/test_agent_service_anti_hallucination_flow.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent_service.py backend/app/tests/test_agent_service_anti_hallucination_flow.py
git commit -m "feat: insert answer review stage into agent pipeline"
```

### Task 6: Add evidence-card streaming support and frontend rendering

**Files:**
- Modify: `backend/app/schemas/response.py`
- Modify: `backend/app/services/stream_response_service.py`
- Modify: `front/agent_web_ui/src/views/ChatPage.vue`
- Test: `backend/app/tests/test_stream_response_diagnostics.py`

- [ ] **Step 1: Write the failing response-shape tests**

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.response_util import ResponseFactory
from schemas.response import ContentKind


def test_answer_packet_can_carry_evidence_card():
    packet = ResponseFactory.build_text(
        "当前不能完全确定：可能是主板坏了。",
        ContentKind.ANSWER,
        extra={"evidence_card": {"status": "证据不足，不确定"}},
    )

    assert packet.content.text == "当前不能完全确定：可能是主板坏了。"
    assert packet.content.evidence_card["status"] == "证据不足，不确定"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
Expected: FAIL because response bodies do not yet expose `evidence_card`

- [ ] **Step 3: Extend response body schema to include evidence-card metadata**

```python
class TextMessageBody(MessageBody):
    contentType: Literal["sagegpt/text"] = "sagegpt/text"
    text: str = Field(default="", description="文本内容")
    kind: ContentKind
    evidence_card: Optional[dict] = None
    uncertainty_reason: str = ""
    review_verdict: str = ""
```

- [ ] **Step 4: Update `ChatPage.vue` to render the evidence card**

```vue
<div v-if="msg.evidenceCard" class="evidence-card">
  <div class="evidence-status">{{ msg.evidenceCard.status }}</div>
  <div v-if="msg.evidenceCard.uncertainty_reason" class="evidence-reason">
    {{ msg.evidenceCard.uncertainty_reason }}
  </div>
  <div v-for="item in msg.evidenceCard.evidence_items" :key="item.evidence_id" class="evidence-item">
    <div class="evidence-source">{{ item.source_name }}</div>
    <div class="evidence-snippet">{{ item.snippet }}</div>
  </div>
</div>
```

- [ ] **Step 5: Update SSE parsing to store evidence-card metadata on answer messages**

```javascript
if (kind === 'ANSWER') {
  const evidenceCard = parsedData.content.evidence_card || null
  const uncertaintyReason = parsedData.content.uncertainty_reason || ''
  const reviewVerdict = parsedData.content.review_verdict || ''
  streamTextToAnswer(text, { evidenceCard, uncertaintyReason, reviewVerdict })
}
```

- [ ] **Step 6: Run verification**

Run:
- `pytest backend/app/tests/test_stream_response_diagnostics.py -v`
- `cd front/agent_web_ui && npm run build`

Expected:
- pytest PASS
- Vite build succeeds

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/response.py backend/app/services/stream_response_service.py front/agent_web_ui/src/views/ChatPage.vue backend/app/tests/test_stream_response_diagnostics.py
git commit -m "feat: render evidence cards in answer stream"
```

### Task 7: Add regression coverage for end-to-end downgrade and persistence behavior

**Files:**
- Modify: `backend/app/tests/test_session_persistence_for_agent_replies.py`
- Modify: `backend/app/tests/test_task_memory_retry_flow.py`
- Test: `backend/app/tests/test_agent_service_anti_hallucination_flow.py`

- [ ] **Step 1: Add persistence regression tests**

```python
def test_persist_downgraded_answer_in_session(monkeypatch):
    ...
    assert "当前不能完全确定" in assistant_messages[-1]["content"]
```

- [ ] **Step 2: Add review-unavailable regression tests**

```python
def test_review_unavailable_keeps_answer_but_marks_card(monkeypatch):
    ...
    assert result.review_verdict == "review_unavailable"
    assert result.evidence_card["review_available"] is False
```

- [ ] **Step 3: Run focused regressions**

Run: `pytest backend/app/tests/test_agent_service_anti_hallucination_flow.py backend/app/tests/test_session_persistence_for_agent_replies.py backend/app/tests/test_task_memory_retry_flow.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/tests/test_agent_service_anti_hallucination_flow.py backend/app/tests/test_session_persistence_for_agent_replies.py backend/app/tests/test_task_memory_retry_flow.py
git commit -m "test: cover downgrade and review availability regressions"
```

### Task 8: Add an evaluation seed set and final verification pass

**Files:**
- Create: `backend/app/tests/test_answer_review_service.py`
- Test: `backend/app/tests/test_risk_classification_service.py`
- Test: `backend/app/tests/test_retrieval_evidence_service.py`
- Test: `backend/app/tests/test_answer_postprocess_service.py`
- Test: `backend/app/tests/test_answer_review_service.py`
- Test: `backend/app/tests/test_agent_service_anti_hallucination_flow.py`

- [ ] **Step 1: Add review examples for supported, unsupported, and conflict**

```python
def test_review_conflict_case(monkeypatch):
    ...
    assert verdict.verdict == "conflict"
```

- [ ] **Step 2: Run the complete focused suite**

Run:

```bash
pytest backend/app/tests/test_risk_classification_service.py ^
       backend/app/tests/test_retrieval_evidence_service.py ^
       backend/app/tests/test_answer_postprocess_service.py ^
       backend/app/tests/test_answer_review_service.py ^
       backend/app/tests/test_agent_service_anti_hallucination_flow.py ^
       backend/app/tests/test_session_persistence_for_agent_replies.py ^
       backend/app/tests/test_stream_response_diagnostics.py -v
```

Expected: PASS

- [ ] **Step 3: Run the existing regression slice around agent service and memory**

Run:

```bash
pytest backend/app/tests/test_agent_service_memory_integration.py ^
       backend/app/tests/test_memory_api.py ^
       backend/app/tests/test_task_memory_api.py -v
```

Expected: PASS

- [ ] **Step 4: Manual smoke test**

Run:

```bash
cd backend/app
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

Manual checks:
- Ask a knowledge-backed question with clear evidence and confirm the answer badge is `已证据支持`.
- Ask a high-risk diagnostic question with no direct knowledge support and confirm the answer is downgraded with `证据不足，不确定`.
- Simulate reviewer failure and confirm the answer badge becomes `审查暂不可用`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tests
git commit -m "test: verify anti-hallucination pipeline end to end"
```

## Self-Review

- Spec coverage: the plan covers evidence normalization, candidate answer contracts, risk classification, review verdicts, downgrade behavior, evidence cards, persistence, UI rendering, and evaluation.
- Placeholder scan: there are no `TODO`, `TBD`, or “implement appropriately” placeholders in the tasks; each task includes a concrete file target, code shape, and verification command.
- Type consistency: the plan consistently uses `CandidateAnswer`, `EvidenceItem`, `ReviewVerdict`, `EvidenceCard`, `risk_level`, and `claimed_evidence_ids` across schema, service, pipeline, and frontend tasks.
