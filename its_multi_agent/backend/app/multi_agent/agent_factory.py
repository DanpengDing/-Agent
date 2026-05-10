import json
from typing import Optional

from agents import Runner, function_tool
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.run import RunConfig

from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import baidu_mcp_client
from multi_agent.service_agent import comprehensive_service_agent
from multi_agent.technical_agent import technical_agent


def collect_tool_diagnostic(tool_name: str, output_text: str) -> Optional[str]:
    text = str(output_text or "").strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
    except Exception:
        lowered = text.lower()
        if "error" in lowered or "exception" in lowered or "failed" in lowered or "异常" in text:
            return f"{tool_name}: {text[:1000]}"
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("needs_user_location"):
        ask_user = payload.get("ask_user") or payload.get("error")
        if ask_user:
            return f"ASK_USER:{ask_user}"

    is_error = payload.get("ok") is False or payload.get("status") == "error"
    error_message = payload.get("error") or payload.get("error_msg") or payload.get("message")
    if is_error or error_message:
        detail = error_message or json.dumps(payload, ensure_ascii=False, default=str)
        return f"{tool_name}: {detail}"

    return None


def format_service_agent_diagnostics(final_output: str, diagnostics: list[str]) -> str:
    if not diagnostics:
        return final_output

    ask_user = next((item[len("ASK_USER:") :] for item in diagnostics if item.startswith("ASK_USER:")), None)
    if ask_user:
        return ask_user

    detail_lines = "\n".join(f"- {item}" for item in diagnostics)
    return f"{final_output}\n\n后端错误详情：\n{detail_lines}"


@function_tool
async def consult_technical_expert(query: str) -> str:
    return await _run_technical_agent_with_logging(query)


async def _run_technical_agent_with_logging(query: str) -> str:
    try:
        logger.info("[Route] technical expert query=%s", query[:200])
        streaming_result = Runner.run_streamed(
            starting_agent=technical_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True),
        )

        async for _event in streaming_result.stream_events():
            pass

        final_output = streaming_result.final_output or ""
        logger.info("[Route] technical expert result=%s", str(final_output)[:500])
        return final_output
    except Exception as exc:
        logger.error("[Route] technical expert failed query=%s error=%s", query, exc, exc_info=True)
        return f"咨询技术专家失败：{exc}"


async def _run_service_agent_with_logging(query: str) -> str:
    await _refresh_service_agent_mcp_connection()
    streaming_result = Runner.run_streamed(
        starting_agent=comprehensive_service_agent,
        input=query,
        run_config=RunConfig(tracing_disabled=True),
    )
    diagnostics: list[str] = []

    async for event in streaming_result.stream_events():
        if event.type != "run_item_stream_event":
            continue

        if hasattr(event, "name") and event.name == "tool_called":
            if isinstance(event.item, ToolCallItem) and event.item.type == "tool_call_item":
                tool_name = event.item.raw_item.name
                tool_args = getattr(event.item.raw_item, "arguments", "")
                logger.info(
                    "[ServiceAgent] tool_called query=%s tool=%s args=%s",
                    query[:100],
                    tool_name,
                    str(tool_args)[:1000],
                )

        elif hasattr(event, "name") and event.name == "tool_output":
            output_item = event.item
            tool_name = getattr(output_item, "tool_name", None) or getattr(output_item, "name", "unknown")
            output_text = getattr(output_item, "output", "")
            if isinstance(output_item, ToolCallOutputItem):
                output_text = output_item.output

            logger.info(
                "[ServiceAgent] tool_output query=%s tool=%s output=%s",
                query[:100],
                tool_name,
                str(output_text)[:1500],
            )
            diagnostic = collect_tool_diagnostic(tool_name, str(output_text))
            if diagnostic:
                diagnostics.append(diagnostic)

    final_output = streaming_result.final_output or ""
    final_output = format_service_agent_diagnostics(final_output, diagnostics)
    logger.info("[ServiceAgent] final_output query=%s output=%s", query[:100], str(final_output)[:1500])
    return final_output


async def _refresh_service_agent_mcp_connection() -> None:
    try:
        await baidu_mcp_client.cleanup()
    except Exception as exc:
        logger.info("[ServiceAgent] cleanup stale baidu mcp ignored: %s", exc)

    await baidu_mcp_client.connect()
    logger.info("[ServiceAgent] baidu mcp reconnected before query")


@function_tool(needs_approval=True)
async def query_service_station_and_navigate(query: str) -> str:
    try:
        logger.info("[Route] service station query=%s", query[:200])
        result_text = await _run_service_agent_with_logging(query)
        logger.info("[Route] service station result=%s", str(result_text)[:1000])
        return result_text
    except Exception as exc:
        logger.error("[Route] service station failed query=%s error=%s", query, exc, exc_info=True)
        return f"服务站查询失败。\n\n后端错误详情：\n- query_service_station_and_navigate: {exc}"


AGENT_TOOLS = [
    consult_technical_expert,
    query_service_station_and_navigate,
]
