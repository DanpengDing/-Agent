from openai import OpenAI
from  dotenv import load_dotenv
import os


# 加载环境变量
load_dotenv()


# 创建客户端 - 需要传入api_key和base_url
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)


# API调用（创建响应）
response = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL_NAME"),
    messages=[
        {"role": "system", "content": "你是一个专业的Python开发人员"},
        {
            "role": "user",
            "content": "如何检查Python对象是否是类的实例？",
        },
    ],
)

print(response.choices[0].message.content)