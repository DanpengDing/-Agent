import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen-plus"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(True)

async def main():
    agent = Agent(
        name="Assistant",
        instructions="你只会用七言绝句回应.",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    )

    result = Runner.run_streamed(agent, "给我写一首关于春天的七言绝句")

    print("\n===== 实时流式输出开始 =====\n")

    async for event in result.stream_events(): # 必须使用async for来迭代流事件
        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)

    print("\n\n===== 流结束 =====")
    print("最终完整结果：", result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
