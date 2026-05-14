from typing import AsyncGenerator

from agents.run import Runner
from fastapi import Query
from fastapi.routing import APIRouter
from opentelemetry.trace import SpanKind
from starlette.responses import StreamingResponse

from infrastructure.logging.logger import logger
from infrastructure.tracing import get_tracer
from multi_agent.orchestrator_agent import orchestrator_agent
from schemas.request import ChatMessageRequest, HumanApprovalRequest, UserPreferenceUpsertRequest, UserSessionsRequest
from schemas.response import ContentKind
from services.agent_service import MultiAgentService
from services.approval_details_service import build_service_station_approval_details
from services.guardrail_service import guardrail_service
from services.hitl_service import hitl_service
from services.memory_service import memory_service
from services.session_service import session_service
from services.task_memory_service import task_memory_service
from services.stream_response_service import extract_backend_error_details_from_result
from services.structured_output_service import structured_output_service
from utils.response_util import ResponseFactory

router = APIRouter()


@router.post("/api/query", summary="query multi agent")
async def query(request_context: ChatMessageRequest) -> StreamingResponse:
    tracer = get_tracer("multi-agent-api")
    user_id = request_context.context.user_id
    user_query = request_context.query
    session_id = request_context.context.session_id or ""

    with tracer.start_as_current_span(
        "agent.query",
        kind=SpanKind.INTERNAL,
        attributes={
            "user.id": user_id,
            "session.id": session_id,
            "query.length": len(user_query),
            "query_preview": user_query[:100] if user_query else "",
        },
    ) as span:
        check_result = guardrail_service.check_input(user_query)
        if check_result.blocked:
            span.set_attribute("guardrail.blocked", True)
            span.set_attribute("guardrail.matched_words", str(check_result.matched_common))
            return StreamingResponse(
                content=_blocked_stream(check_result),
                status_code=200,
                media_type="text/event-stream",
            )

        if check_result.replaced:
            user_query = check_result.filtered_text
            span.set_attribute("guardrail.replaced", True)
            span.set_attribute("guardrail.business_words", str(check_result.matched_business))
            logger.info(
                "Guardrail: user=%s business_words=%s replaced_query=%s",
                user_id,
                check_result.matched_business,
                user_query,
            )

        logger.info("user=%s query=%s", user_id, user_query)
        async_generator_result = MultiAgentService.process_task(request_context, flag=True)
        return StreamingResponse(
            content=async_generator_result,
            status_code=200,
            media_type="text/event-stream",
        )


async def _blocked_stream(check_result) -> AsyncGenerator[str, None]:
    blocked_words = ", ".join(check_result.matched_common)
    text = f"检测到不允许的内容：{blocked_words}。请换一种说法再试。"
    yield "data: " + ResponseFactory.build_text(
        text,
        ContentKind.PROCESS,
    ).model_dump_json() + "\n\n"
    yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"


@router.post("/api/human_approval", summary="resume a paused run after human approval")
async def human_approval(request: HumanApprovalRequest) -> StreamingResponse:
    approval = hitl_service.resolve_pending_approval(
        token=request.approval_token,
        user_id=request.context.user_id,
        session_id=request.context.session_id or "",
        decision=request.decision,
    )

    async def approval_stream():
        if approval.decision == "rejected":
            task = task_memory_service.find_task_by_approval_token(
                user_id=request.context.user_id,
                session_id=request.context.session_id or "",
                token=approval.token,
            )
            if task:
                task_memory_service.mark_cancelled(
                    user_id=request.context.user_id,
                    task_id=task["task_id"],
                    reason="用户拒绝审批",
                )
            rejected_text = "已取消这次操作。如需继续，我可以换一种方式帮你。"
            session_service.append_and_save_message(
                user_id=request.context.user_id,
                session_id=request.context.session_id or "",
                role="assistant",
                content=rejected_text,
            )
            hitl_service.consume_approval(approval.token)
            yield "data: " + ResponseFactory.build_text(
                rejected_text,
                ContentKind.PROCESS,
            ).model_dump_json() + "\n\n"
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
            return

        try:
            if approval.state is None:
                raise ValueError("pending approval state is missing")

            task = task_memory_service.find_task_by_approval_token(
                user_id=request.context.user_id,
                session_id=request.context.session_id or "",
                token=approval.token,
            )
            if task:
                task_memory_service.mark_resumed_after_approval(
                    user_id=request.context.user_id,
                    task_id=task["task_id"],
                )

            for interruption in approval.interruptions:
                approval.state.approve(interruption)

            result = await Runner.run(orchestrator_agent, approval.state)
            interruptions = list(getattr(result, "interruptions", None) or [])
            if interruptions:
                to_state = getattr(result, "to_state", None)
                next_state = to_state() if callable(to_state) else getattr(result, "state", None)
                next_pending = hitl_service.create_pending_approval(
                    user_id=request.context.user_id,
                    session_id=request.context.session_id or "",
                    query=approval.query,
                    state=next_state,
                    interruptions=interruptions,
                    title="需要你的确认",
                    question="继续执行这次操作吗？",
                    details=build_service_station_approval_details(approval.query),
                    approve_label="继续",
                    reject_label="取消",
                )
                logger.info(
                    "[Approval] resumed run created next interruption token=%s count=%d",
                    next_pending.token,
                    len(interruptions),
                )
                if task:
                    task_memory_service.mark_waiting_approval(
                        user_id=request.context.user_id,
                        task_id=task["task_id"],
                        approval_token=next_pending.token,
                        details=next_pending.details or "",
                    )
                approval_message = MultiAgentService._format_approval_message(
                    next_pending.question,
                    next_pending.details,
                )
                if approval_message:
                    session_service.append_and_save_message(
                        user_id=request.context.user_id,
                        session_id=request.context.session_id or "",
                        role="assistant",
                        content=approval_message,
                    )
                yield "data: " + ResponseFactory.build_human_approval(
                    token=next_pending.token,
                    title=next_pending.title,
                    question=next_pending.question,
                    details=next_pending.details,
                    approve_label=next_pending.approve_label,
                    reject_label=next_pending.reject_label,
                ).model_dump_json() + "\n\n"
                yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
                return

            final_output = result.final_output or ""
            structured_output = structured_output_service.parse_final_output(final_output)
            for backend_error_detail in extract_backend_error_details_from_result(result):
                yield "data: " + ResponseFactory.build_text(
                    backend_error_detail,
                    ContentKind.PROCESS,
                ).model_dump_json() + "\n\n"
            logger.info(
                "[Approval] resumed run token=%s final_output=%s structured_intent=%s",
                approval.token,
                final_output[:1000],
                structured_output.intent,
            )
            if structured_output.answer:
                session_service.append_and_save_message(
                    user_id=request.context.user_id,
                    session_id=request.context.session_id or "",
                    role="assistant",
                    content=structured_output.answer,
                )
                if task:
                    task_memory_service.mark_completed(
                        user_id=request.context.user_id,
                        task_id=task["task_id"],
                        summary=structured_output.answer,
                    )
            yield "data: " + ResponseFactory.build_text(
                structured_output.answer,
                ContentKind.ANSWER,
            ).model_dump_json() + "\n\n"
        finally:
            hitl_service.consume_approval(approval.token)

        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    return StreamingResponse(
        content=approval_stream(),
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/api/user_sessions")
def get_user_sessions(request: UserSessionsRequest):
    user_id = request.user_id
    logger.info("fetch sessions for user=%s", user_id)
    try:
        all_sessions = session_service.get_all_sessions_memory(user_id)
        return {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(all_sessions),
            "sessions": all_sessions,
        }
    except Exception as exc:
        logger.error("fetch sessions failed user=%s error=%s", user_id, exc)
        return {
            "success": False,
            "user_id": user_id,
            "error": str(exc),
        }


@router.get("/api/memories/long-term")
def get_long_term_memories(user_id: str = Query(...), limit: int = Query(20, ge=1, le=100)):
    try:
        items = memory_service.list_long_term_memories(user_id, limit=limit)
        return {
            "success": True,
            "user_id": user_id,
            "total": len(items),
            "items": items,
        }
    except Exception as exc:
        logger.error("fetch long-term memories failed user=%s error=%s", user_id, exc)
        return {"success": False, "user_id": user_id, "error": str(exc)}


@router.get("/api/memories/preferences")
def get_user_preferences(user_id: str = Query(...), limit: int = Query(20, ge=1, le=100)):
    try:
        items = memory_service.list_user_preferences(user_id, limit=limit)
        return {
            "success": True,
            "user_id": user_id,
            "total": len(items),
            "items": items,
        }
    except Exception as exc:
        logger.error("fetch preferences failed user=%s error=%s", user_id, exc)
        return {"success": False, "user_id": user_id, "error": str(exc)}


@router.put("/api/memories/preferences")
def upsert_user_preference(request: UserPreferenceUpsertRequest):
    try:
        memory_service.set_user_preference(
            user_id=request.user_id,
            preference_key=request.preference_key,
            preference_value=request.preference_value,
            session_id=request.session_id or "",
        )
        return {
            "success": True,
            "user_id": request.user_id,
            "preference_key": request.preference_key,
            "preference_value": request.preference_value,
        }
    except Exception as exc:
        logger.error("upsert preference failed user=%s key=%s error=%s", request.user_id, request.preference_key, exc)
        return {
            "success": False,
            "user_id": request.user_id,
            "preference_key": request.preference_key,
            "error": str(exc),
        }


@router.delete("/api/memories/preferences/{preference_key}")
def delete_user_preference(preference_key: str, user_id: str = Query(...)):
    try:
        deleted = memory_service.delete_user_preference(user_id=user_id, preference_key=preference_key)
        return {
            "success": True,
            "user_id": user_id,
            "preference_key": preference_key,
            "deleted": deleted,
        }
    except Exception as exc:
        logger.error("delete preference failed user=%s key=%s error=%s", user_id, preference_key, exc)
        return {
            "success": False,
            "user_id": user_id,
            "preference_key": preference_key,
            "error": str(exc),
        }


@router.get("/api/memories/tasks/active")
def get_active_task(user_id: str = Query(...), session_id: str = Query("")):
    try:
        item = task_memory_service.get_active_task(user_id=user_id, session_id=session_id or "")
        return {
            "success": True,
            "user_id": user_id,
            "session_id": session_id,
            "item": item,
        }
    except Exception as exc:
        logger.error("fetch active task failed user=%s session=%s error=%s", user_id, session_id, exc)
        return {"success": False, "user_id": user_id, "session_id": session_id, "error": str(exc)}


@router.get("/api/memories/tasks")
def get_task_memories(user_id: str = Query(...), session_id: str = Query(""), limit: int = Query(20, ge=1, le=100)):
    try:
        items = task_memory_service.list_tasks(user_id=user_id, session_id=session_id or "", limit=limit)
        return {
            "success": True,
            "user_id": user_id,
            "session_id": session_id,
            "total": len(items),
            "items": items,
        }
    except Exception as exc:
        logger.error("fetch task memories failed user=%s session=%s error=%s", user_id, session_id, exc)
        return {"success": False, "user_id": user_id, "session_id": session_id, "error": str(exc)}


@router.get("/api/memories/tasks/{task_id}")
def get_task_memory_detail(task_id: str, user_id: str = Query(...)):
    try:
        item = task_memory_service.get_task(user_id=user_id, task_id=task_id)
        return {
            "success": True,
            "user_id": user_id,
            "task_id": task_id,
            "item": item,
        }
    except Exception as exc:
        logger.error("fetch task memory detail failed user=%s task_id=%s error=%s", user_id, task_id, exc)
        return {"success": False, "user_id": user_id, "task_id": task_id, "error": str(exc)}
