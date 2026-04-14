


# 1.导入相关依赖
from langchain_openai import ChatOpenAI

from   langchain.chat_models import  init_chat_model

from  dotenv import load_dotenv
load_dotenv()

import  os

# 2.获取api_key和base_url
# api_key= os.getenv("DASHSCOPE_API_KEY")
# base_url=os.getenv("DASHSCOPE_API_BASE")


api_key= os.getenv("OPENAI_API_KEY")
base_url=os.getenv("OPENAI_API_BASE")
model=os.getenv("OPEN_LLM_NAME")

# 3.实例化模型
# llm = ChatOpenAI(model_name=model,openai_api_key=api_key ,openai_api_base=base_url)

llm=init_chat_model(model="deepseek-chat",model_provider="deepseek",api_key="sk-4fba30f4e19a40f08b752e3279f96e56",base_url="https://api.deepseek.com")

# 4.调用模型
response=llm.invoke("请给我讲一个幽默的笑话")
print(response)
