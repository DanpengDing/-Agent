from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from agents import (
    Agent,
    Model,
    ModelProvider,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    function_tool,
    set_tracing_disabled,
)

BASE_URL =  "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME =  "qwen-plus"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)

# 1. 自定义ModelProvider类，实现ModelProvider接口的get_model方法
class CustomModelProvider(ModelProvider):

     # 实现ModelProvider接口的get_model方法
    def get_model(self, model_name: str) -> Model:

        return OpenAIChatCompletionsModel(model= model_name, openai_client=client) # 直接返回OpenAIChatCompletionsModel  不用在调用set_default_openai_api("chat_completions")设置默认api为chat_completions


# 2. 创建CustomModelProvider实例
CUSTOM_MODEL_PROVIDER = CustomModelProvider()

async def main():
    # 3. 使用CustomModelProvider实例创建Agent
    agent = Agent(name="Assistant", instructions="你只会用七言绝句回应.",model=MODEL_NAME) # 要指定model_name为MODEL_NAME 这样get_model方法才能获取到model_name

    # 4. 运行Agent
    result = await Runner.run(
        agent,
        input="给我写一首关于春天的七言绝句",
        run_config=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER),

    )
    # 5. 获取Agent运行结果
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())