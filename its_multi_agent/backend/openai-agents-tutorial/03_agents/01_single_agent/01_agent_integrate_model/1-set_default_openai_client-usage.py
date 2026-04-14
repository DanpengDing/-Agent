import asyncio
from openai import AsyncOpenAI

from agents import (
    Agent,
    Runner,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)

BASE_URL ="https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen-plus"

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY
)
set_default_openai_client(client=client)    # 设置默认client为custom client
set_default_openai_api("chat_completions")  # 设置默认api为chat_completions
set_tracing_disabled(disabled=True)  # 禁用tracing


async def main():
    agent = Agent(
        name="Assistant",
        instructions="你只会用七言绝句回应",
        model=MODEL_NAME,
    )
    result = await Runner.run(agent, "给我写一首关于春天的七言绝句")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
