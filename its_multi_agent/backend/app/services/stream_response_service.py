import json
from collections.abc import AsyncGenerator

from agents.items import ToolCallItem
from agents.run import RunResultStreaming
from openai.types.responses.response_stream_event import (
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseTextDeltaEvent,
)

from infrastructure.logging.logger import logger
from schemas.response import ContentKind
from services.structured_output_service import structured_output_service
from services.tool_failure_service import tool_failure_service
from utils.response_util import ResponseFactory
from utils.text_util import format_agent_update_html, format_tool_call_html

BACKEND_ERROR_MARKER = "后端错误详情："


def extract_backend_error_details(output: str):
    text = str(output or "")
    index = text.find(BACKEND_ERROR_MARKER)
    if index < 0:
        return None
    return text[index:].strip()


def extract_backend_error_details_from_result(result) -> list:
    details = []
    for attr_name in ("new_items", "items", "generated_items"):
        for item in getattr(result, attr_name, None) or []:
            output = getattr(item, "output", None)
            if output is None:
                raw_item = getattr(item, "raw_item", None)
                output = getattr(raw_item, "output", None) if raw_item is not None else None
            detail = extract_backend_error_details(str(output or ""))
            if detail and detail not in details:
                details.append(detail)
    return details


def try_parse_tool_output(output):
    if isinstance(output, dict):
        return output

    text = str(output or "").strip()
    if not text or not text.startswith("{"):
        return None

    try:
        return json.loads(text)
    except Exception:
        return None


def extract_tool_failure_from_output(tool_name: str, output):
    payload = try_parse_tool_output(output)
    if not isinstance(payload, dict):
        return None
    return tool_failure_service.classify_payload(tool_name, payload)


def _has_structured_answer_metadata(structured_output) -> bool:
    return bool(
        getattr(structured_output, "review_verdict", None) is not None
        or getattr(structured_output, "evidence_cards", None)
        or getattr(structured_output, "references", None)
        or getattr(structured_output, "next_action", None)
        or getattr(structured_output, "intent", None)
    )


async def process_stream_response(
    streaming_result: RunResultStreaming,
    callbacks: dict | None = None,
) -> AsyncGenerator:
    callbacks = callbacks or {}
    answer_delta_seen = False

    async for event in streaming_result.stream_events():
        logger.debug("[Stream] event type=%s", event.type)

        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                delta_text = event.data.delta
                answer_delta_seen = True
                logger.debug("[Stream] answer delta=%s", delta_text[:200])
                yield "data: " + ResponseFactory.build_text(
                    delta_text,
                    ContentKind.ANSWER,
                ).model_dump_json() + "\n\n"
            elif ResponseReasoningTextDeltaEvent and isinstance(event.data, ResponseReasoningTextDeltaEvent):
                if event.data.delta:
                    logger.debug("[Stream] reasoning delta=%s", event.data.delta[:200])
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta,
                        ContentKind.THINKING,
                    ).model_dump_json() + "\n\n"
            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                if event.data.delta:
                    logger.debug("[Stream] reasoning summary delta=%s", event.data.delta[:200])
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta,
                        ContentKind.THINKING,
                    ).model_dump_json() + "\n\n"

        elif event.type == "run_item_stream_event":
            if hasattr(event, "name") and event.name == "tool_called":
                if isinstance(event.item, ToolCallItem) and event.item.type == "tool_call_item":
                    tool_name = event.item.raw_item.name
                    tool_args = getattr(event.item.raw_item, "arguments", "")
                    logger.info("[Stream] tool_called name=%s args=%s", tool_name, str(tool_args)[:500])
                    callback = callbacks.get("on_tool_called")
                    if callable(callback):
                        callback(tool_name, str(tool_args))

                    text = format_tool_call_html(tool_name)
                    yield "data: " + ResponseFactory.build_text(
                        text,
                        ContentKind.PROCESS,
                    ).model_dump_json() + "\n\n"

            elif hasattr(event, "name") and event.name == "tool_output":
                output = getattr(event.item, "output", "")
                logger.info("[Stream] tool_output=%s", str(output)[:1000])

                output_callback = callbacks.get("on_tool_output")
                if callable(output_callback):
                    output_callback(str(output))

                tool_name_lookup = callbacks.get("tool_name_lookup", lambda: "unknown")
                tool_name = tool_name_lookup() if callable(tool_name_lookup) else "unknown"
                failure = extract_tool_failure_from_output(tool_name, output)
                if failure is not None:
                    failure_callback = callbacks.get("on_tool_failure")
                    if callable(failure_callback):
                        failure_callback(failure)
                    continue

                details = extract_backend_error_details(str(output))
                if details:
                    yield "data: " + ResponseFactory.build_text(
                        details,
                        ContentKind.PROCESS,
                    ).model_dump_json() + "\n\n"

        elif event.type == "agent_updated_stream_event":
            new_agent_name = event.new_agent.name
            logger.info("[Stream] agent_updated new_agent=%s", new_agent_name)

            text = format_agent_update_html(new_agent_name)
            yield "data: " + ResponseFactory.build_text(
                text,
                ContentKind.PROCESS,
            ).model_dump_json() + "\n\n"

    structured_output = structured_output_service.parse_final_output(
        getattr(streaming_result, "final_output", None)
    )
    if structured_output.answer or _has_structured_answer_metadata(structured_output):
        yield "data: " + ResponseFactory.build_text(
            "" if answer_delta_seen else structured_output.answer,
            ContentKind.ANSWER,
            review_verdict=structured_output.review_verdict,
            evidence_cards=structured_output.evidence_cards,
            references=structured_output.references,
            next_action=structured_output.next_action,
            intent=structured_output.intent,
        ).model_dump_json() + "\n\n"

    logger.info("[Stream] finished")
