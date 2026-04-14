import asyncio


from openai import AsyncOpenAI

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from agents.items import ResponseOutputItem,MessageOutputItem



# 调式
# 通用模型
# 阿里云 qwen3-max (通用大模型)
# 定位：对标 GPT-4o 的通用旗舰模型。
# 特点 (System 1)：它的训练目标是准确、高效地给出最终答案。虽然它内部有很强的逻辑推理能力，但它倾向于直接输出结果，或者把推理过程内化了（隐式推理）。
# 表现：
# 它不会把“思考过程”作为单独的数据流吐出来。
# 它返回的只有 content（最终回复）。、
# 因此，你在 SDK 里只能看到 MessageOutputItem，看不到 ReasoningItem。

# SiliconFlow 的 Qwen (如果是推理变体)
# 定位：目前开源界流行的是 DeepSeek-R1 或 QwQ (Qwen with Questions) 这类 推理模型 (Reasoning Models)。
# 特点 (System 2)：这类模型使用了强化学习（RL），被强制训练为“先思考（Chain of Thought），再回答”。
# 表现：
# 它会显式通过 API 的 reasoning_content 字段返回思考过程。
# 为什么“有时思考，有时不思考”？
# 问题简单：如果问题太简单（比如“你是谁”），部分推理模型会跳过思考直接回答。
# 模型版本：SiliconFlow 上有很多版本。如果调用的是 Qwen/Qwen2.5-32B-Instruct（普通版），它通常不思考；如果你调用的是 Qwen/QwQ-32B 或 DeepSeek-R1-Distill-Qwen-32B，它就会思考。


# qwen3-max模型
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen3-max"


# Qwen/Qwen3-32B模型
# BASE_URL = "https://api.siliconflow.cn/v1"
# API_KEY =  "sk-vnxijjgodhcjisacoilnebjzzlqmrwyuluqdxcpwauocgqjm"
# MODEL_NAME = "Qwen/Qwen3-32B"


# gpt-5-x模型
# BASE_URL = "https://api.openai-proxy.org/v1"
# API_KEY =  "sk-3fNNVrOHy9YbLm87IQZdCe9VZDI9rA5CcCRfe9Nw2w9yyEAT"
# # MODEL_NAME = "gpt-5.2-pro"
# MODEL_NAME = "gpt-5-nano"


client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)





async def main():
    agent = Agent(
        name="天气助手",
        instructions="你是一个天气助手，你只能回答关于天气的问题。",
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    )
    result = await Runner.run(agent, "北京的天气")

    for item in result.new_items:
        print(item)
        # if isinstance(item, MessageOutputItem):
        #     print("模型回答【原始事件】:", item.raw_item)
        #     print("模型回答（原始事件内容）:", item.raw_item.content)

    print(f"Agent最终输出: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())