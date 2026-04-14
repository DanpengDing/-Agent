from openai import OpenAI
from  dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 创建客户端 - 需要传入api_key和base_url
client = OpenAI(
    # api_key=os.getenv("SF_API_KEY"),
    # base_url=os.getenv("SF_BASE_URL"),
    api_key=os.getenv("AL_BAILIAN_API_KEY"),
    base_url=os.getenv("AL_BAILIAN_BASE_URL"),
)

# API调用（创建响应）
response = client.chat.completions.create(
    # model=os.getenv("SF_MODEL_NAME"),
    model=os.getenv("AL_BAILIAN_MODEL_NAME"),
    messages=[
        {"role": "system", "content": "你是一个乐于助人的助手"},
        {
            "role": "user",
            "content": "你是谁？",
        },
    ],
)

print(response.choices[0].message.content)