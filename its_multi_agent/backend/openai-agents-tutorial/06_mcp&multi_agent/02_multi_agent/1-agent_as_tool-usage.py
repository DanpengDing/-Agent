import asyncio
from openai import AsyncOpenAI

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
    set_tracing_disabled,
    ModelSettings,
)

from openai.types.responses import ResponseTextDeltaEvent


# ====== OpenAI-compatible 配置（以 DashScope/Qwen 示例）======
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen3-max"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


# ====== 1) 底层真实工具（这里用 function_tool 演示，实际可连真实天气 API）======
@function_tool
def get_weather(city: str) -> str:
    """查询天气（演示：写死）"""
    return f"{city}：晴，24℃，风力2级"

@function_tool
def get_air_quality(city: str) -> str:
    """查询空气质量（演示：写死）"""
    return f"{city}：AQI 55（良），PM2.5 18"


# ====== 2) 专家 Agents（作为工具被 manager 调用）======
weather_expert_agent = Agent(
    name="Weather expert",
    instructions=(
        "你是天气查询专家。"
        "用户一旦问天气，你必须调用 get_weather 工具获取结果。"
        "输出务必简短：直接返回工具结果，不要额外扩写。"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_weather],
    model_settings=ModelSettings(tool_choice="required"),
)

aqi_expert_agent = Agent(
    name="AQI expert",
    instructions=(
        "你是空气质量查询专家。"
        "用户问空气质量/AQI/PM2.5，必须调用 get_air_quality 工具获取结果。"
        "输出务必简短：直接返回工具结果，不要额外扩写。"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_air_quality],
    model_settings=ModelSettings(tool_choice="required"),
)


# ====== 3) Manager / Customer-facing Agent（总控：统一口径）======
customer_facing_agent = Agent(
    name="Customer-facing agent",
    instructions=(
        "你是客服总控，负责与用户对话并统一口径。\n"
        "规则：\n"
        "1) 用户问【天气】-> 必须调用 weather_expert 工具；\n"
        "2) 用户问【空气质量/AQI/PM2.5】-> 必须调用 aqi_expert 工具；\n"
        "3) 如果用户没说城市，先追问城市；\n"
        "4) 最终答复要口语化，能把专家输出组织成一句话。\n"
        "禁止编造真实数据，必须依赖专家工具返回。\n"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[
        weather_expert_agent.as_tool(
            tool_name="weather_expert",
            tool_description="天气专家：负责查询天气并返回结果",
        ),
        aqi_expert_agent.as_tool(
            tool_name="aqi_expert",
            tool_description="空气质量专家：负责查询AQI/PM2.5并返回结果",
        ),
    ],
    # 让 manager 必须选择工具（课堂演示更稳定）
    model_settings=ModelSettings(tool_choice="required"),
)


async def main():
    user_question = "武汉天气怎么样？顺便空气质量呢？"

    result = Runner.run_streamed(customer_facing_agent, user_question)

    print("\n=== STREAM EVENTS ===")

    async for event in result.stream_events():
        # 1) 工具调用事件（manager 调用专家工具 / 专家再调用底层工具）
        if event.type == "run_item_stream_event":
            name = getattr(event, "name", None)

            if name == "tool_called":
                # 工具名 & 参数
                tool_name = event.item.raw_item.name
                tool_args = event.item.raw_item.arguments
                print(f"\n✅ tool_called: {tool_name} args={tool_args}")

            elif name == "tool_output":
                # 工具输出
                out = event.item.output
                print(f"\n✅ tool_output: {out}")

            elif name == "message_output_created":
                # assistant 开始创建消息
                msg = event.item.raw_item
                print(f"\n🧾 message_output_created: role={getattr(msg, 'role', None)}")

        # 2) 文本流（最终客服的回复会以 delta 形式出来）
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)

        # 3) agent 更新事件（handoff 才常见；manager 模式一般不会切换）
        if event.type == "agent_updated_stream_event":
            print("\n👤 agent_updated:", event.new_agent.name)

    print("\n\n=== FINAL OUTPUT ===")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
