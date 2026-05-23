import re
import traceback
from collections.abc import AsyncGenerator

from agents.run import RunConfig, Runner
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from infrastructure.logging.logger import logger
from infrastructure.tracing import get_tracer
from multi_agent.orchestrator_agent import orchestrator_agent
from schemas.answer_review import ReviewVerdict
from schemas.request import ChatMessageRequest
from schemas.response import ContentKind
from services.approval_details_service import build_service_station_approval_details
from services.answer_postprocess_service import answer_postprocess_service
from services.answer_review_service import answer_review_service
from services.hitl_service import hitl_service
from services.memory_service import memory_service
from services.query_rewrite_service import query_rewrite_service
from services.retrieval_evidence_service import retrieval_evidence_service
from services.risk_classification_service import risk_classification_service
from services.session_service import session_service
from services.stream_response_service import process_stream_response
from services.structured_output_service import structured_output_service
from services.task_memory_service import task_memory_service
from services.tool_failure_service import tool_failure_service
from utils.response_util import ResponseFactory


class MultiAgentService:
    @staticmethod
    def _format_approval_message(question: str, details: str | None = None) -> str:
        message = (question or "").strip()
        extra = (details or "").strip()
        if not extra:
            return message
        return f"{message}\n\n{extra}"

    @staticmethod
    def _normalize_final_output(raw_output: str):
        return structured_output_service.parse_final_output(raw_output)

    @staticmethod
    def _review_and_finalize_output(query: str, raw_output, active_task):
        candidate_answer = structured_output_service.parse_candidate_output(raw_output)
        evidence_items = retrieval_evidence_service.normalize_task_payload(active_task)
        classification = risk_classification_service.classify(query, candidate_answer, evidence_items)
        review_verdict = MultiAgentService._safe_review_candidate(
            candidate_answer=candidate_answer,
            evidence_items=evidence_items,
            should_review=classification.should_review,
        )
        return answer_postprocess_service.finalize(candidate_answer, review_verdict, evidence_items)

    @staticmethod
    def _safe_review_candidate(candidate_answer, evidence_items, should_review: bool) -> ReviewVerdict:
        if not should_review:
            return ReviewVerdict(
                status="supported",
                summary="Review skipped for low-risk answer.",
                should_downgrade=False,
                reviewed=False,
            )
        try:
            return answer_review_service.review_answer(candidate_answer, evidence_items)
        except Exception as exc:
            logger.warning("[AgentService] answer review fallback triggered error=%s", exc)
            return ReviewVerdict(
                status="review_unavailable",
                summary=f"Review unavailable: {exc}",
                should_downgrade=True,
                reviewed=False,
            )

    @staticmethod
    def _build_session_message_extra_fields(structured_result) -> dict:
        extra_fields = {}
        if getattr(structured_result, "review_verdict", None) is not None:
            extra_fields["review_verdict"] = structured_result.review_verdict.model_dump()
        if getattr(structured_result, "evidence_cards", None):
            extra_fields["evidence_cards"] = [card.model_dump() for card in structured_result.evidence_cards]
        if getattr(structured_result, "references", None):
            extra_fields["references"] = list(structured_result.references)
        if getattr(structured_result, "next_action", None):
            extra_fields["next_action"] = structured_result.next_action
        if getattr(structured_result, "intent", None):
            extra_fields["intent"] = structured_result.intent
        return extra_fields

    @staticmethod
    def _extract_interruptions(result) -> list:
        interruptions = getattr(result, "interruptions", None)
        return list(interruptions) if interruptions else []

    @staticmethod
    def _extract_state(result):
        to_state = getattr(result, "to_state", None)
        if callable(to_state):
            return to_state()
        return getattr(result, "state", None)

    @staticmethod
    def _resolve_tool_failure_policy(failure):
        if failure.action.value == "RETRY_TOOL":
            return {
                "should_retry_task": True,
                "should_block_task": False,
                "should_return_user_message": True,
            }
        if failure.action.value == "ASK_USER_CLARIFY":
            return {
                "should_retry_task": False,
                "should_block_task": False,
                "should_return_user_message": True,
            }
        return {
            "should_retry_task": False,
            "should_block_task": True,
            "should_return_user_message": True,
        }

    @classmethod
    async def process_task(cls, request: ChatMessageRequest, flag: bool) -> AsyncGenerator[str, None]:
        tracer = get_tracer("multi-agent-service")
        user_id = request.context.user_id
        session_id = request.context.session_id or ""
        original_query = request.query
        user_query = original_query
        active_task = None
        recovered_task = None

        try:
            logger.info(
                "[AgentService] start user=%s session=%s retry=%s skip_user_message=%s query=%s",
                user_id,
                session_id,
                flag,
                request.skip_user_message,
                original_query,
            )

            with tracer.start_as_current_span(
                "query_rewrite",
                kind=SpanKind.INTERNAL,
                attributes={
                    "user.id": user_id,
                    "session.id": session_id,
                    "query.original": original_query,
                },
            ) as span:
                runtime_state = await session_service.load_runtime_state(
                    user_id=user_id,
                    session_id=session_id,
                    pending_user_input=original_query,
                )
                base_history = session_service.build_runtime_history(runtime_state, append_user_message=False)
                rewrite_result = await query_rewrite_service.rewrite(original_query, base_history)
                user_query = rewrite_result.rewritten_query
                span.set_attribute("query.rewritten", user_query)
                span.set_attribute("query.history_length", len(base_history))

            memory_service.capture_user_memory(
                user_id=user_id,
                session_id=session_id,
                text=original_query,
            )
            memory_messages = memory_service.build_memory_system_messages(user_id)
            recovered_task = task_memory_service.get_active_task_for_query(user_id, session_id, user_query)
            active_task = recovered_task or task_memory_service.ensure_task(user_id, session_id, user_query)
            chat_history = session_service.build_runtime_history(
                runtime_state,
                user_input=user_query,
                append_user_message=not request.skip_user_message,
            )
            if memory_messages:
                first_non_system_index = next(
                    (index for index, item in enumerate(chat_history) if item.get("role") != "system"),
                    len(chat_history),
                )
                chat_history = (
                    chat_history[:first_non_system_index]
                    + memory_messages
                    + chat_history[first_non_system_index:]
                )
            if recovered_task:
                first_non_system_index = next(
                    (index for index, item in enumerate(chat_history) if item.get("role") != "system"),
                    len(chat_history),
                )
                chat_history = (
                    chat_history[:first_non_system_index]
                    + task_memory_service.build_resume_system_messages(recovered_task)
                    + chat_history[first_non_system_index:]
                )

            if not request.skip_user_message:
                runtime_state = session_service.append_message_to_state(runtime_state, "user", user_query)
                session_service.save_session_state(user_id, session_id, runtime_state)

            for chunk in build_process_chunks(query_rewrite_service.build_process_message(rewrite_result)):
                yield chunk

            callbacks_state = {"last_tool_failure": None}

            with tracer.start_as_current_span(
                "orchestrator.run",
                kind=SpanKind.INTERNAL,
                attributes={
                    "user.id": user_id,
                    "session.id": session_id,
                    "orchestrator.max_turns": 5,
                    "chat_history.length": len(chat_history),
                },
            ):
                streaming_result = Runner.run_streamed(
                    starting_agent=orchestrator_agent,
                    input=chat_history,
                    context=user_query,
                    max_turns=5,
                    run_config=RunConfig(tracing_disabled=True),
                )

                callbacks = {}
                if active_task:
                    callbacks = {
                        "on_tool_called": lambda tool_name, tool_args: task_memory_service.record_tool_called(
                            user_id=user_id,
                            task_id=active_task["task_id"],
                            tool_name=tool_name,
                        ),
                        "on_tool_output": lambda output: task_memory_service.record_tool_output(
                            user_id=user_id,
                            task_id=active_task["task_id"],
                            tool_name=(task_memory_service.get_task(user_id, active_task["task_id"]) or {}).get("last_tool_name", "unknown"),
                            output_text=output,
                        ),
                        "tool_name_lookup": lambda: (task_memory_service.get_task(user_id, active_task["task_id"]) or {}).get("last_tool_name", "unknown"),
                        "on_tool_failure": lambda failure: (
                            callbacks_state.__setitem__("last_tool_failure", failure),
                            task_memory_service.record_tool_failure(
                                user_id=user_id,
                                task_id=active_task["task_id"],
                                failure=failure,
                            ),
                        )[-1],
                    }

                async for chunk in process_stream_response(streaming_result, callbacks=callbacks):
                    yield chunk

            interruptions = cls._extract_interruptions(streaming_result)
            if interruptions:
                with tracer.start_as_current_span(
                    "hitl.approval_required",
                    kind=SpanKind.INTERNAL,
                    attributes={
                        "user.id": user_id,
                        "session.id": session_id,
                        "hitl.interruption_count": len(interruptions),
                    },
                ):
                    state = cls._extract_state(streaming_result)
                    pending = hitl_service.create_pending_approval(
                        user_id=user_id,
                        session_id=session_id,
                        query=user_query,
                        state=state,
                        interruptions=interruptions,
                        title="需要人工确认",
                        question="是否允许智能体查询维修站并继续执行？",
                        details=build_service_station_approval_details(user_query),
                        approve_label="允许查询",
                        reject_label="取消操作",
                    )
                    if active_task:
                        task_memory_service.mark_waiting_approval(
                            user_id=user_id,
                            task_id=active_task["task_id"],
                            approval_token=pending.token,
                            details=pending.details or "",
                        )

                    approval_message = cls._format_approval_message(pending.question, pending.details)
                    if approval_message:
                        session_service.append_and_save_message(
                            user_id=user_id,
                            session_id=session_id,
                            role="assistant",
                            content=approval_message,
                        )

                    yield "data: " + ResponseFactory.build_human_approval(
                        token=pending.token,
                        title=pending.title,
                        question=pending.question,
                        details=pending.details,
                        approve_label=pending.approve_label,
                        reject_label=pending.reject_label,
                    ).model_dump_json() + "\n\n"
                    yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
                    return

            failure = callbacks_state.get("last_tool_failure")
            if failure is not None:
                session_service.append_and_save_message(
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=failure.user_message,
                )
                policy = cls._resolve_tool_failure_policy(failure)
                if policy["should_return_user_message"]:
                    yield "data: " + ResponseFactory.build_text(
                        failure.user_message,
                        ContentKind.PROCESS,
                    ).model_dump_json() + "\n\n"

                if policy["should_retry_task"] and flag:
                    if active_task:
                        task_memory_service.mark_retrying(
                            user_id=user_id,
                            task_id=active_task["task_id"],
                            error=failure.developer_message or failure.error_code,
                        )
                    async for item in MultiAgentService.process_task(request, flag=False):
                        yield item
                    return

                if policy["should_block_task"] and active_task:
                    task_memory_service.mark_blocked(
                        user_id=user_id,
                        task_id=active_task["task_id"],
                        error=failure.developer_message or failure.error_code,
                    )

                yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
                return

            agent_result = streaming_result.final_output or ""
            structured_result = cls._review_and_finalize_output(user_query, agent_result, active_task)
            formatted_result = re.sub(r"\n+", "\n", structured_result.answer)
            runtime_state = session_service.append_message_to_state(runtime_state, "assistant", formatted_result)
            runtime_state = session_service.attach_extra_fields_to_last_message(
                runtime_state,
                cls._build_session_message_extra_fields(structured_result),
            )
            session_service.save_session_state(user_id, session_id, runtime_state)
            if active_task:
                task_memory_service.mark_completed(
                    user_id=user_id,
                    task_id=active_task["task_id"],
                    summary=formatted_result,
                )
            yield "data: " + ResponseFactory.build_text(
                formatted_result,
                ContentKind.ANSWER,
                review_verdict=structured_result.review_verdict,
                evidence_cards=structured_result.evidence_cards,
                references=structured_result.references,
                next_action=structured_result.next_action,
                intent=structured_result.intent,
            ).model_dump_json() + "\n\n"
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

        except Exception as exc:
            logger.error(
                "[AgentService] failed user=%s session=%s query=%s error=%s",
                user_id,
                session_id,
                original_query,
                exc,
            )
            logger.debug("[AgentService] traceback=%s", traceback.format_exc())

            span = trace.get_current_span()
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))

            text = f"系统处理请求时出现异常：{exc}"
            yield "data: " + ResponseFactory.build_text(text, ContentKind.PROCESS).model_dump_json() + "\n\n"

            failure = tool_failure_service.classify_exception("runner", exc)
            policy = cls._resolve_tool_failure_policy(failure)

            if flag and policy["should_retry_task"]:
                if active_task:
                    task_memory_service.mark_retrying(
                        user_id=user_id,
                        task_id=active_task["task_id"],
                        error=str(exc),
                    )
                retry_text = "正在尝试自动重试一次，请稍候。"
                yield "data: " + ResponseFactory.build_text(retry_text, ContentKind.PROCESS).model_dump_json() + "\n\n"
                async for item in MultiAgentService.process_task(request, flag=False):
                    yield item
            else:
                if active_task:
                    task_memory_service.mark_blocked(
                        user_id=user_id,
                        task_id=active_task["task_id"],
                        error=str(exc),
                    )
                yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"


def build_process_chunks(message: str):
    if not message:
        return
    yield "data: " + ResponseFactory.build_text(message, ContentKind.PROCESS).model_dump_json() + "\n\n"
