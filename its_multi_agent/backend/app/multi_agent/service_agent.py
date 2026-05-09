from agents import Agent, ModelSettings, set_tracing_disabled

from infrastructure.ai.openai_client import sub_model
from infrastructure.ai.prompt_loader import load_prompt
from infrastructure.tools.local.service_station import (
    map_uri,
    query_nearest_repair_shops_by_coords,
    resolve_user_location_from_text,
)
from infrastructure.tools.mcp.mcp_servers import baidu_mcp_client

set_tracing_disabled(True)


SERVICE_AGENT_EXTRA_RULES = """

硬性规则：
1. 先调用 `resolve_user_location_from_text` 判断用户当前位置。
2. 如果工具返回 `needs_user_location=true`，必须立即追问用户位置。
3. 追问示例：请告诉我你现在在哪个城市、区县、商圈，或者直接发一个具体地址，我再帮你查最近的电脑维修服务站。
4. 禁止在位置不明时使用默认坐标、猜测城市，或继续查询最近服务站。
"""


comprehensive_service_agent = Agent(
    name="全能业务智能体",
    instructions=load_prompt("comprehensive_service_agent") + SERVICE_AGENT_EXTRA_RULES,
    model=sub_model,
    model_settings=ModelSettings(
        temperature=0,
        max_tokens=2048,
    ),
    tools=[
        resolve_user_location_from_text,
        query_nearest_repair_shops_by_coords,
        map_uri,
    ],
    mcp_servers=[baidu_mcp_client],
)


async def run_single_test(case_name: str, input_text: str):
    from agents import Runner, ToolCallItem, ToolCallOutputItem

    print(f"\n{'=' * 80}")
    print(f"测试场景: {case_name}")
    print(f"输入问题: \"{input_text}\"")
    print("-" * 80)
    try:
        await baidu_mcp_client.connect()
        result = Runner.run_streamed(
            starting_agent=comprehensive_service_agent,
            input=input_text,
        )

        async for event in result.stream_events():
            if event.type != "run_item_stream_event":
                continue

            if getattr(event, "name", "") == "tool_called" and isinstance(event.item, ToolCallItem):
                raw_item = event.item.raw_item
                print(f"\n调用工具名: {raw_item.name} ---> 工具参数: {raw_item.arguments}")
            elif getattr(event, "name", "") == "tool_output" and isinstance(event.item, ToolCallOutputItem):
                print(f"工具输出结果: {event.item.output}")

        print(f"\n\nAgent 最终输出: {result.final_output}")
    except Exception as exc:
        print(f"\nError: {exc}\n")
    finally:
        try:
            await baidu_mcp_client.cleanup()
        except Exception:
            pass


async def main():
    test_cases = [
        ("缺少位置时追问", "我要修电脑"),
    ]

    for name, question in test_cases:
        await run_single_test(name, question)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
