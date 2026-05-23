from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from schemas.answer_review import EvidenceCard, ReviewVerdict


class ContentKind(str, Enum):
    THINKING = "THINKING"
    PROCESS = "PROCESS"
    ANSWER = "ANSWER"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


class StreamStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class StopReason(str, Enum):
    NORMAL = "NORMAL"
    MAX_TOKENS = "MAX_TOKENS"
    ERROR = "ERROR"


class MessageBody(BaseModel):
    contentType: str


class TextMessageBody(MessageBody):
    contentType: Literal["sagegpt/text"] = "sagegpt/text"
    text: str = Field(default="", description="Text payload")
    kind: ContentKind
    review_verdict: Optional[ReviewVerdict] = None
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    intent: Optional[str] = None


class HumanApprovalBody(MessageBody):
    contentType: Literal["sagegpt/human_approval"] = "sagegpt/human_approval"
    kind: Literal[ContentKind.HUMAN_APPROVAL] = ContentKind.HUMAN_APPROVAL
    token: str
    title: str
    question: str
    approveLabel: str = "确认"
    rejectLabel: str = "取消"
    details: Optional[str] = None


class FinishMessageBody(MessageBody):
    contentType: Literal["sagegpt/finish"] = "sagegpt/finish"


class PacketMeta(BaseModel):
    createTime: str
    finishReason: Optional[StopReason] = None
    errorMessage: Optional[str] = None


class StreamPacket(BaseModel):
    id: str
    content: Union[TextMessageBody, HumanApprovalBody, FinishMessageBody]
    status: StreamStatus
    metadata: PacketMeta
