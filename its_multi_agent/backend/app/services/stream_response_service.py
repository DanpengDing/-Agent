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
from utils.response_util import ResponseFactory
from utils.text_util import format_agent_update_html, format_tool_call_html


def extract_backend_error_details(output: str):
    text = str(output or "")
    marker = "后端错误详情："
    index = text.find(marker)
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


async def process_stream_response(streaming_result: RunResultStreaming, callbacks: dict | None = None) -> AsyncGenerator:
    callbacks = callbacks or {}
    async for event in streaming_result.stream_events():
        logger.debug("[Stream] event type=%s", event.type)

        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                delta_text = event.data.delta
                logger.debug("[Stream] answer delta=%s", delta_text[:200])
                yield "data: " + ResponseFactory.build_text(
                    delta_text, ContentKind.ANSWER
                ).model_dump_json() + "\n\n"

            elif ResponseReasoningTextDeltaEvent and isinstance(event.data, ResponseReasoningTextDeltaEvent):
                if event.data.delta:
                    logger.debug("[Stream] reasoning delta=%s", event.data.delta[:200])
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta, ContentKind.THINKING
                    ).model_dump_json() + "\n\n"

            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                if event.data.delta:
                    logger.debug("[Stream] reasoning summary delta=%s", event.data.delta[:200])
                    yield "data: " + ResponseFactory.build_text(
                        event.data.delta, ContentKind.THINKING
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
                        text, ContentKind.PROCESS
                    ).model_dump_json() + "\n\n"

            elif hasattr(event, "name") and event.name == "tool_output":
                output = getattr(event.item, "output", "")
                logger.info("[Stream] tool_output=%s", str(output)[:1000])
                callback = callbacks.get("on_tool_output")
                if callable(callback):
                    callback(str(output))
                details = extract_backend_error_details(str(output))
                if details:
                    yield "data: " + ResponseFactory.build_text(
                        details, ContentKind.PROCESS
                    ).model_dump_json() + "\n\n"

        elif event.type == "agent_updated_stream_event":
            new_agent_name = event.new_agent.name
            logger.info("[Stream] agent_updated new_agent=%s", new_agent_name)

            text = format_agent_update_html(new_agent_name)
            yield "data: " + ResponseFactory.build_text(
                text, ContentKind.PROCESS
            ).model_dump_json() + "\n\n"

    logger.info("[Stream] finished")
