import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled

BASE_URL = "https://api.siliconflow.cn/v1"
API_KEY = "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
MODEL_NAME = "Qwen/Qwen3-32B"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
# 建议先把 disable=True 打开，避免干扰
set_tracing_disabled(disabled=True)


@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    print(f"  >>> [工具调用] 正在查询 {city} 的天气...")
    return f"{city}是晴天，气温 28 度"


async def main():
    agent = Agent(
        name="天气助手",
        instructions="你是一个天气助手，负责查询天气。",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather],
    )

    print("=== 第一轮：询问天气 ===")
    # 1. 第一轮运行
    result1 = await Runner.run(agent, "武汉的天气怎么样？")
    print(f"Agent回复: {result1.final_output}\n")

    # 2. 生成历史记录列表
    history = result1.to_input_list()

    print("=== 🔍 审查 to_input_list() 的内容 ===")
    # 我们遍历打印一下，看看里面到底存了什么
    for i, item in enumerate(history):

        print(f"[{i}] | 内容: {item}...")

    print("\n=== 第二轮：基于历史继续追问 ===")
    # 3. 模拟多轮对话
    # 我们直接把刚才生成的 history 列表传给下一次 run
    # 并在后面追加一个新的用户问题
    new_input = history + [{"role": "user", "content": "那这种天气适合去跑步吗？"}]

    result2 = await Runner.run(agent, new_input)
    print(f"Agent回复: {result2.final_output}")


if __name__ == "__main__":
    asyncio.run(main())