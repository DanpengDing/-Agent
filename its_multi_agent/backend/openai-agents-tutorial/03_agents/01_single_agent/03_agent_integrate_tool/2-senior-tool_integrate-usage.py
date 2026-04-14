import asyncio
import json
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from pydantic import BaseModel

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY =  "sk-26d57c968c364e7bb14f1fc350d4bff0"
MODEL_NAME = "qwen-plus"

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
set_tracing_disabled(disabled=True)


# json('{'name':'zs','age':18}')--->对象(User(name: age:))----dict
# json--->对象---Map

class WeatherResult(BaseModel):
    city: str
    condition: str
    source: str
    message: str

@function_tool
def get_weather(city: str) -> str:
    return json.dumps(
        {"city": city, "condition": "晴", "source": "tool", "message": f"{city}天气晴朗"},
        ensure_ascii=False,
    )

async def main():
    agent = Agent(
        name="天气助手",
        instructions=(
            "你是天气助手，只回答天气问题。"
            "当用户问天气时必须调用 get_weather。"
        ),
        model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
        tools=[get_weather],
        output_type=WeatherResult,
    )

    result = await Runner.run(agent, "武汉的天气")
    # result.final_output 不再是 str，而是 WeatherResult（或可当作 dict 使用）
    print("final_output:", result.final_output)

    # 如果你想转 dict --- model_dump对象转成一个字典

    print("as dict:", result.final_output.model_dump())

if __name__ == '__main__':
    asyncio.run(main())
