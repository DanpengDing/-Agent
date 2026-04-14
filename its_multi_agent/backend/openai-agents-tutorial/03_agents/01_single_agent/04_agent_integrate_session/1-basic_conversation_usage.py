import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, SQLiteSession, Runner, set_tracing_disabled

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen3-max"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)

# Create agent
agent = Agent(
    name="Assistant",
    instructions="回答要非常简洁",
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client)
)

# Create a session instance(会话id)
session = SQLiteSession("conversation_123")

async def first_turn():
    result = await Runner.run(
        agent,
        "金门大桥在哪个城市",
        session=session
    )
    print(f"Turn 1 Output: {result.final_output}")

async def second_turn():
    result = await Runner.run(
        agent,
        "我刚刚问了什么？",
        session=session
    )
    print(f"Turn 2 Output: {result.final_output}")

# 修改为异步函数，保持一致性
async def third_turn():
    # 这里原本是 run_sync，在 async main 中最好统一用 await Runner.run
    result = await Runner.run(
        agent,
        "它的人口是多少？",
        session=session
    )
    print(f"Turn 3 Output: {result.final_output}")

async def get_items():
    print("--- Session Items ---")
    items = await session.get_items()
    for it in items:
        print(it)

# ---统一的主入口 ---
async def main():
    # 依次执行，共用同一个事件循环
    await first_turn()
    await second_turn()
    await third_turn()
    # await get_items()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass