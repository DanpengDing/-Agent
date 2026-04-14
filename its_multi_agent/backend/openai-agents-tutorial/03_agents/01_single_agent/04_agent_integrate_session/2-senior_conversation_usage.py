import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, SQLiteSession, Runner, set_tracing_disabled, function_tool

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen3-max"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"天气信息: {city} 是晴天"

# Create agent
agent = Agent(
    name="Assistant",
    instructions="你是一个天气助手，只回答天气问题。当用户问天气时必须调用 get_weather。",
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[get_weather],
)

# Create a session instance with a session ID
# 注意：两个 Session 使用同一个数据库文件 'conversation_123.db'，但 session_id 不同
session_user1 = SQLiteSession("user123", "conversation_123.db")
session_user2 = SQLiteSession("user1234", "conversation_123.db")

# First turn (User 1)
async def first_turn():
    print("\n--- User 1: 问天气 ---")
    result = await Runner.run(
        agent,
        "武汉的天气怎么样？",
        session=session_user1
    )
    print(f"Agent: {result.final_output}")

# Second turn (User 1)
async def second_turn():
    print("\n--- User 1: 追问 ---")
    result = await Runner.run(
        agent,
        "我刚刚问了什么？",
        session=session_user1
    )
    print(f"Agent: {result.final_output}")

# Third turn (User 1)
async def third_turn():
    print("\n--- User 1: 问函数调用 ---")
    # 【修正点】：改为 await Runner.run
    result = await Runner.run(
        agent,
        "你刚刚调用了什么函数？",
        session=session_user1
    )
    print(f"Agent: {result.final_output}")

# Four turn (User 2) 测试不同用户隔离
async def four_turn():
    print("\n--- User 2: 问函数调用 (全新上下文) ---")
    # 【修正点】：改为 await Runner.run
    # 注意：这里使用的是 session_user2
    result = await Runner.run(
        agent,
        "你刚刚调用了什么函数？",
        session=session_user2
    )
    print(f"Agent: {result.final_output}")

# ---统一的主入口 ---
async def main():
    # 依次执行，共用同一个事件循环
    await first_turn()
    await second_turn()
    await third_turn()
    await four_turn()

if __name__ == "__main__":
    asyncio.run(main())