import asyncio


from openai import AsyncOpenAI

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen-plus"

# 1. 创建AsyncOpenAI客户端实例
client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)

async def main():
    # 2. 创建Agent实例
    agent = Agent(
        name="Assistant",
        instructions="你只会用七言绝句回应.",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client), # 3.通过Agent的model参数指定使用OpenAIChatCompletionsModel
    )

    # 4. 运行Agent
    result = await Runner.run(agent, "给我写一首关于春天的七言绝句")

    # 5. 获取Agent运行结果
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())