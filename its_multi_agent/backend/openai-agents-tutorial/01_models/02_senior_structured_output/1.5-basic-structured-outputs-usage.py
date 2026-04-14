from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os


class Person(BaseModel):
    name: str
    age: int



# 加载环境变量
load_dotenv()


# 创建客户端 - 需要传入api_key和base_url
client = OpenAI(
    api_key=os.getenv("AL_BAILIAN_API_KEY"),
    base_url=os.getenv("AL_BAILIAN_BASE_URL"),
)


response = client.chat.completions.parse(
  model=os.getenv("AL_BAILIAN_MODEL_NAME"),
  messages=[
    {
      "role": "user",
      "content": "Jane, 54 years old",
    }
  ],
  response_format=Person,

)

print(response.choices[0].message.content)
