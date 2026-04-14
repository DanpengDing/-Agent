import asyncio
from openai import AsyncOpenAI

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
    set_tracing_disabled,
    ModelSettings,
    SQLiteSession,
)
from openai.types.responses import ResponseTextDeltaEvent, ResponseReasoningSummaryTextDeltaEvent


# ====== OpenAI-compatible 配置（以 DashScope 为例）======
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen-plus"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)


# ====== 工具：不再使用 Context ======
@function_tool
def get_weather(city: str) -> str:
    return f"{city}：晴，24℃，风力2级"


async def main():
    # 1) Agent
    agent = Agent(
        name="天气助手",
        instructions=(
            "你是天气助手。\n"
            "当用户询问天气时，必须调用 get_weather 工具获取结果，禁止编造。\n"
            "如果用户没说城市，请追问用户城市。\n"
        ),
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather],
        model_settings=ModelSettings(tool_choice="required"),
    )

    # 2) Session：落盘到 conversations.db
    session = SQLiteSession("user_001_weather_chat", "conversations1.db")

    # ------------------ 第一轮（streamed） ------------------
    print("\n=== TURN 1 (streamed) ===")
    result = Runner.run_streamed(
        agent,
        "武汉的天气怎么样？",
        session=session,
    )

    async for event in result.stream_events():

        # A) RunItemStreamEvent：工具调用 / 工具结果 / 消息创建
        if event.type == "run_item_stream_event":
            if getattr(event, "name", None) == "tool_called":
                print("\n✅ tool_called:", event.item.raw_item.name, "args=", event.item.raw_item.arguments)
            elif getattr(event, "name", None) == "tool_output":
                print("\n✅ tool_output:", event.item.output)
            elif getattr(event, "name", None) == "message_output_created":
                msg = event.item.raw_item
                print(f"\n🧾 message_output_created: msg:{msg}")

        # B) RawResponsesStreamEvent：文本 / 推理增量
        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)
            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                pass

        # C) AgentUpdatedStreamEvent
        if event.type == "agent_updated_stream_event":
            print("\n👤 agent_updated_stream_event:", event.new_agent.name)

    print("\n\nfinal_output:", result.final_output)

    # ------------------ 验证：session 中是否包含 tool call ------------------
    print("\n=== VERIFY session items ===")
    items = await session.get_items()
    print("session total items =", len(items))

    for i, it in enumerate(items, 1):
        print(it)
    # # ------------------ 第二轮（非流式） ------------------
    print("\n=== TURN 2 (non-stream) ===")
    result2 = await Runner.run(
        agent,
        "我刚刚问了你什么？",
        session=session,
    )
    print("final_output:", result2.final_output)

    print("\n Done. conversations.db 已写入（包含 tool calls / outputs / messages）。")


if __name__ == "__main__":
    asyncio.run(main())
