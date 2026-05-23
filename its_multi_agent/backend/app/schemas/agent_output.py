from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.answer_review import EvidenceCard, ReviewVerdict


class StructuredAgentOutput(BaseModel):
    intent: str = Field(default="general")
    answer: str = Field(default="")
    references: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    evidence_cards: List[EvidenceCard] = Field(default_factory=list)
    review_verdict: Optional[ReviewVerdict] = None
