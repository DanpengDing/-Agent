import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, Literal, Optional


@dataclass
class HumanApprovalRequired(Exception):
    title: str
    question: str
    details: Optional[str] = None
    approve_label: str = "确认"
    reject_label: str = "取消"


@dataclass
class PendingApproval:
    token: str
    user_id: str
    session_id: str
    query: str
    title: str
    question: str
    details: Optional[str]
    approve_label: str
    reject_label: str
    decision: Optional[Literal["approved", "rejected"]] = None


@dataclass
class HitlRunContext:
    user_id: str
    session_id: str
    query: str
    approval_token: Optional[str] = None
    approval_decision: Optional[Literal["approved", "rejected"]] = None


_run_context: ContextVar[Optional[HitlRunContext]] = ContextVar("hitl_run_context", default=None)


class HitlService:
    def __init__(self):
        self._pending: Dict[str, PendingApproval] = {}

    def set_context(self, context: HitlRunContext):
        return _run_context.set(context)

    def reset_context(self, token):
        _run_context.reset(token)

    def require_approval(
        self,
        title: str,
        question: str,
        details: Optional[str] = None,
        approve_label: str = "确认",
        reject_label: str = "取消",
    ) -> None:
        current = _run_context.get()
        if current is None:
            raise RuntimeError("HITL context is not initialized")

        if current.approval_decision == "approved" and current.approval_token:
            approval = self._pending.get(current.approval_token)
            if approval and approval.decision == "approved":
                return

        raise HumanApprovalRequired(
            title=title,
            question=question,
            details=details,
            approve_label=approve_label,
            reject_label=reject_label,
        )

    def create_pending_approval(
        self,
        user_id: str,
        session_id: str,
        query: str,
        required: HumanApprovalRequired,
    ) -> PendingApproval:
        token = str(uuid.uuid4())
        approval = PendingApproval(
            token=token,
            user_id=user_id,
            session_id=session_id or "",
            query=query,
            title=required.title,
            question=required.question,
            details=required.details,
            approve_label=required.approve_label,
            reject_label=required.reject_label,
        )
        self._pending[token] = approval
        return approval

    def resolve_pending_approval(
        self,
        token: str,
        user_id: str,
        session_id: str,
        decision: Literal["approved", "rejected"],
    ) -> PendingApproval:
        approval = self._pending.get(token)
        if approval is None:
            raise ValueError("审批已失效或不存在")
        if approval.user_id != user_id:
            raise ValueError("审批用户不匹配")
        if (approval.session_id or "") != (session_id or ""):
            raise ValueError("审批会话不匹配")

        approval.decision = decision
        return approval

    def consume_approval(self, token: str) -> None:
        self._pending.pop(token, None)


hitl_service = HitlService()
