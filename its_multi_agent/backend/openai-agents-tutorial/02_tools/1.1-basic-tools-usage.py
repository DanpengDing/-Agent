from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# 加载环境变量
load_dotenv()

# 创建客户端
client = OpenAI(
    api_key=os.getenv("AL_BAILIAN_API_KEY"),
    base_url=os.getenv("AL_BAILIAN_BASE_URL"),
)


# 定义工具函数
def get_weather(city: str) -> str:
    """模拟查询天气函数"""
    weather_data = {
        "北京": "北京：晴天，15-25°C，适宜外出",
        "上海": "上海：多云，18-28°C，微风",
        "广州": "广州：阵雨，22-30°C，记得带伞",
        "深圳": "深圳：晴转多云，23-31°C，湿度较高"
    }
    return weather_data.get(city, f"暂无{city}的天气信息")


# 使用底层JSON方式定义工具
def chat_with_basic_tools():
    print("=== 1. 底层方式：手动编写工具定义 ===")

    messages = [
        {"role": "system", "content": "你是一个天气助手，可以查询天气信息。"},
        {"role": "user", "content": "我想知道北京的天气怎么样？"}
    ]

    response = client.chat.completions.create(
        model=os.getenv("AL_BAILIAN_MODEL_NAME"),
        messages=messages,
        tools=[{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询指定城市的天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称，如'北京'、'上海'",
                        },
                    },
                    "required": ["city"],
                    "additionalProperties": False
                },
            }
        }],
    )

    message = response.choices[0].message
    messages.append(message)

    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "get_weather":
                args = json.loads(tool_call.function.arguments)
                result = get_weather(args["city"])

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        second_response = client.chat.completions.create(
            model=os.getenv("AL_BAILIAN_MODEL_NAME"),
            messages=messages,
        )

        print(f"最终回复: {second_response.choices[0].message.content}")

    return response


if __name__ == "__main__":
    chat_with_basic_tools()
