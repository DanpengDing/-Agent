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

# ====== 1) 底层工具（天气与空气质量）======
@function_tool
def get_weather(city: str) -> str:
    return f"{city}：晴，24℃，风力2级"

@function_tool
def get_air_quality(city: str) -> str:
    return f"{city}：AQI 55（良），PM2.5 18"

# ====== 2) 专家 Agents（处理天气与空气质量）======
weather_agent = Agent(
    name="Weather agent",
    instructions=(
        "你是天气专家。\n"
        "1) 如果用户没说城市，先追问城市。\n"
        "2) 如果用户说了城市，调用 get_weather 工具获取结果，禁止编造。\n"
        "3) 输出要口语化、简短。\n"
        "4) 完成天气回答后，必须将控制权交还给 Triage agent，以便继续处理其他问题。\n"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_weather],
    model_settings=ModelSettings(tool_choice="auto"),
)

aqi_agent = Agent(
    name="AQI agent",
    instructions=(
        "你是空气质量专家。\n"
        "1) 如果用户没说城市，先追问城市。\n"
        "2) 如果用户说了城市，调用 get_air_quality 工具获取结果，禁止编造。\n"
        "3) 输出要口语化、简短。\n"
        "4) 完成空气质量回答后，将控制权交还给用户。\n"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_air_quality],
    model_settings=ModelSettings(tool_choice="auto"),
)

# ====== 3) 改进的分诊 Agent ======
triage_agent = Agent(
    name="Triage agent",
    instructions=(
        "你是分诊助手，负责协调多个专家代理回答问题。\n"
        "规则：\n"
        "1. 分析用户问题包含哪些需求：\n"
        "   - 如果包含【天气/温度/下雨/晴天】-> 需要 Weather agent\n"
        "   - 如果包含【空气质量/AQI/PM2.5/雾霾】-> 需要 AQI agent\n"
        "2. 按顺序处理每个需求：\n"
        "   a) 先处理第一个需求，交接给对应的专家代理\n"
        "   b) 等待专家代理完成后，检查是否还有其他未处理的需求\n"
        "   c) 如果有，继续处理下一个需求\n"
        "3. 如果用户同时问天气和空气质量，处理顺序：天气 -> 空气质量\n"
        "4. 你自己不要调用任何工具，也不要自己回答具体数据。\n"
        "5. 确保每个需求都得到处理。\n"
        "6. 在最后一个专家代理完成工作后，结束对话。\n"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    handoffs=[weather_agent, aqi_agent],
)

# 设置双向 handoff 关系
weather_agent.handoffs = [triage_agent]
aqi_agent.handoffs = [triage_agent]

async def main():
    # 用户提出的问题，包含天气和空气质量
    user_question = "武汉天气怎么样？顺便空气质量呢？"

    # 让分诊代理处理问题
    result = Runner.run_streamed(triage_agent, user_question)

    print("\n=== STREAM EVENTS ===")
    async for event in result.stream_events():
        if event.type == "agent_updated_stream_event":
            print(f"\n👤 agent_updated_stream_event -> {event.new_agent.name}")

        if event.type == "run_item_stream_event":
            name = getattr(event, "name", None)

            if name == "tool_called":
                tool_name = event.item.raw_item.name
                print(f"\n✅ tool_called: {tool_name} args={event.item.raw_item.arguments}")

            elif name == "tool_output":
                print(f"\n✅ tool_output: {event.item.output}")

            elif name == "message_output_created":
                msg = event.item.raw_item
                role = getattr(msg, 'role', None)
                content = getattr(msg, 'content', None)
                if content and len(content) > 0:
                    text_content = content[0].text if hasattr(content[0], 'text') else str(content[0])
                    print(f"\n🧾 message_output_created: role={role}, content={text_content[:50]}...")

        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)

    print("\n\n=== FINAL OUTPUT ===")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())