from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ReviewStatus = Literal["supported", "unsupported", "conflicting", "review_unavailable"]
RiskLevel = Literal["low", "medium", "high"]
EvidenceSupportLevel = Literal["supports", "neutral", "conflicts"]


class EvidenceItem(BaseModel):
    source: str = Field(default="retrieval")
    title: Optional[str] = None
    snippet: str = Field(default="")
    uri: Optional[str] = None
    support_level: EvidenceSupportLevel = "neutral"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceCard(BaseModel):
    title: str = Field(default="")
    snippet: str = Field(default="")
    source: str = Field(default="retrieval")
    uri: Optional[str] = None


class CandidateAnswer(BaseModel):
    intent: str = Field(default="general")
    answer: str = Field(default="")
    references: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None


class RiskClassification(BaseModel):
    level: RiskLevel = "low"
    reasons: List[str] = Field(default_factory=list)
    should_review: bool = False


class ReviewVerdict(BaseModel):
    status: ReviewStatus = "supported"
    summary: str = Field(default="")
    should_downgrade: bool = False
    reviewed: bool = True
