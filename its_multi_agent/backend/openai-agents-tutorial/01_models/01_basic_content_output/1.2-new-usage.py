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
response = client.responses.create(
    model=os.getenv("OPENAI_MODEL_NAME"),
    input="写一个关于独角兽的睡前小故事"
)

print(response.output_text)