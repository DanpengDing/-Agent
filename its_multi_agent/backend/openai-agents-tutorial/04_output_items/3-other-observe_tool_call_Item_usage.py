import asyncio


from openai import AsyncOpenAI

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from agents.items import ToolCallItem


# qwen3-max模型
# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
# MODEL_NAME = "qwen3-max"


# Qwen/Qwen3-32B模型
# BASE_URL = "https://api.siliconflow.cn/v1"
# API_KEY =  "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
# MODEL_NAME = "Qwen/Qwen3-32B"


# gpt-5-x模型
BASE_URL = "https://api.openai-proxy.org/v1"
API_KEY =  "sk-3fNNVrOHy9YbLm87IQZdCe9VZDI9rA5CcCRfe9Nw2w9yyEAT"
# MODEL_NAME = "gpt-5.2-pro"
MODEL_NAME = "gpt-5-nano"


client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)


@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"天气信息: {city} 是晴天"


async def main():
    agent = Agent(
        name="天气助手",
        instructions="你是一个天气助手，你只能回答关于天气的问题。",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather]
    )
    result = await Runner.run(agent, "武汉的天气")

    for item in result.new_items:
        print(item)
        if isinstance(item, ToolCallItem):
            print("模型回答【原始事件】:", item.raw_item)
            print("调用工具:", item.raw_item.name)
            print("参数:", item.raw_item.arguments)

    print(f"Agent最终输出: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())