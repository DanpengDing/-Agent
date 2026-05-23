import uuid
from datetime import datetime
from typing import Any, Optional

from schemas.answer_review import EvidenceCard, ReviewVerdict
from schemas.response import (
    ContentKind,
    FinishMessageBody,
    HumanApprovalBody,
    PacketMeta,
    StreamPacket,
    StreamStatus,
    TextMessageBody,
)


class ResponseFactory:
    @staticmethod
    def _normalize_review_verdict(review_verdict: Optional[Any]) -> Optional[ReviewVerdict]:
        if review_verdict is None:
            return None
        if isinstance(review_verdict, ReviewVerdict):
            return review_verdict
        return ReviewVerdict.model_validate(review_verdict)

    @staticmethod
    def _normalize_evidence_cards(evidence_cards: Optional[list[Any]]) -> list[EvidenceCard]:
        if not evidence_cards:
            return []
        return [
            card if isinstance(card, EvidenceCard) else EvidenceCard.model_validate(card)
            for card in evidence_cards
        ]

    @staticmethod
    def build_text(
        text: str,
        kind: ContentKind,
        review_verdict: Optional[Any] = None,
        evidence_cards: Optional[list[Any]] = None,
        references: Optional[list[str]] = None,
        next_action: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> StreamPacket:
        body = TextMessageBody(
            text=text,
            kind=kind,
            review_verdict=ResponseFactory._normalize_review_verdict(review_verdict),
            evidence_cards=ResponseFactory._normalize_evidence_cards(evidence_cards),
            references=list(references or []),
            next_action=next_action,
            intent=intent,
        )
        return StreamPacket(
            id=str(uuid.uuid4()),
            content=body,
            status=StreamStatus.IN_PROGRESS,
            metadata=PacketMeta(createTime=str(datetime.now())),
        )

    @staticmethod
    def build_human_approval(
        token: str,
        title: str,
        question: str,
        details: Optional[str] = None,
        approve_label: str = "确认",
        reject_label: str = "取消",
    ) -> StreamPacket:
        body = HumanApprovalBody(
            token=token,
            title=title,
            question=question,
            details=details,
            approveLabel=approve_label,
            rejectLabel=reject_label,
        )
        return StreamPacket(
            id=str(uuid.uuid4()),
            content=body,
            status=StreamStatus.IN_PROGRESS,
            metadata=PacketMeta(createTime=str(datetime.now())),
        )

    @staticmethod
    def build_finish(message_id: Optional[str] = None) -> StreamPacket:
        return StreamPacket(
            id=message_id or str(uuid.uuid4()),
            content=FinishMessageBody(),
            status=StreamStatus.FINISHED,
            metadata=PacketMeta(createTime=str(datetime.now())),
        )
