from agents import function_tool

from config.settings import settings
from infrastructure.ai.openai_client import sub_model_client
from infrastructure.logging.logger import logger


async def _run_bailian_web_search(query: str) -> str:
    stream = await sub_model_client.chat.completions.create(
        model=settings.SUB_MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是联网搜索助手。请基于实时搜索结果回答用户问题。"
                    "回答要简洁、准确；如果搜索结果不足，请明确说明不确定性。"
                ),
            },
            {"role": "user", "content": query},
        ],
        stream=True,
        extra_body={
            "enable_search": True,
        },
    )

    chunks: list[str] = []
    async for chunk in stream:
        for choice in getattr(chunk, "choices", []) or []:
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None) if delta else None
            if isinstance(content, str):
                chunks.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_value = item.get("text")
                        if text_value:
                            chunks.append(text_value)

    return "".join(chunks).strip()


@function_tool(
    name_override="bailian_web_search",
    description_override=(
        "联网搜索工具。适用于需要最新、实时、互联网信息的问题，比如蓝屏错误、产品现状、新闻、公告、"
        "版本变化、官网说明等。输入应为清晰的搜索问题。"
    ),
)
async def bailian_web_search(query: str) -> str:
    try:
        logger.info("[WebSearch] query=%s", query[:200])
        result = await _run_bailian_web_search(query)
        logger.info("[WebSearch] result=%s", result[:500])
        return result or "未检索到足够的联网搜索结果。"
    except Exception as exc:
        logger.error("[WebSearch] failed query=%s error=%s", query, exc, exc_info=True)
        return f"联网搜索失败：{exc}"
