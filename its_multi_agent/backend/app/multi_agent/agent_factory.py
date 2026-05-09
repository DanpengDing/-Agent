import json
from typing import Optional

from agents import Runner, function_tool
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.run import RunConfig

from infrastructure.logging.logger import logger
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
        if "error" in lowered or "exception" in lowered or "failed" in lowered or "失败" in text:
            return f"{tool_name}: {text[:1000]}"
        return None

    if not isinstance(payload, dict):
        return None

    is_error = payload.get("ok") is False or payload.get("status") == "error"
    error_message = payload.get("error") or payload.get("error_msg") or payload.get("message")
    if is_error or error_message:
        detail = error_message or json.dumps(payload, ensure_ascii=False, default=str)
        return f"{tool_name}: {detail}"

    return None


def format_service_agent_diagnostics(final_output: str, diagnostics: list[str]) -> str:
    if not diagnostics:
        return final_output

    detail_lines = "\n".join(f"- {item}" for item in diagnostics)
    return f"{final_output}\n\n后端错误详情：\n{detail_lines}"


@function_tool
async def consult_technical_expert(query: str) -> str:
    # 这是“主调度智能体 -> 技术专家智能体”的桥接工具。
    # 主调度智能体不会直接调用 technical_agent 对象，
    # 而是通过 function_tool 先进入这里，再由这里手动调用子 Agent。
    try:
        logger.info("[Route] technical expert query=%s", query[:200])
        result = await Runner.run(
            technical_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True),
        )
        logger.info("[Route] technical expert result=%s", str(result.final_output)[:500])
        return result.final_output
    except Exception as exc:
        logger.error("[Route] technical expert failed query=%s error=%s", query, exc, exc_info=True)
        return f"技术专家处理失败：{exc}"


async def _run_service_agent_with_logging(query: str) -> str:
    # 这里显式使用 run_streamed，而不是简单 await Runner.run(...)。
    # 原因不是为了前端流式输出，而是为了在日志里完整记录：
    # 1. 服务站子 Agent 到底调用了哪些工具
    # 2. 每个工具的入参是什么
    # 3. 每个工具的返回值是什么
    # 这样一旦“维修站查不到”，我们就能快速定位是：
    # 路由没进去、定位失败、查库为空，还是模型最后自己兜底改写了答案。
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


@function_tool(needs_approval=True)
async def query_service_station_and_navigate(query: str) -> str:
    # needs_approval=True 是官方 Agents SDK 的审批开关。
    # 这里的含义不是“先执行函数，再问用户要不要继续”，
    # 而是：模型一旦决定调用这个工具，SDK 会先暂停 run，
    #  SDK 把待审批项放到 interruptions，同时给出一个可恢复的 state。
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
