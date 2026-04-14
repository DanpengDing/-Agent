"""
llm_tool模块

该模块提供了通用的llm调用
将llm调用进行封装,在后续调用时只需调用call_llm即可

对所有任务设计的通用模型调用的方法
"""

import  os

from  langchain_openai import  ChatOpenAI
from  langchain_core.prompts import  ChatPromptTemplate
# from  langchain.chat_models import  init_chat_model
from  dotenv import load_dotenv
load_dotenv()




def  call_llm(query:str, system_instruction:str)->str:
    """
    通用LLM处理
    args1:问题
    args2:某个业务对应的提示词是什么

    :return:模型输出结果

    """
    # 1.获取到模型的信息
    api_key=os.getenv("DASHSCOPE_API_KEY")
    api_base=os.getenv("DASHSCOPE_API_BASE")
    model_name=os.getenv("DASHSCOPE_MODEL_NAME")

    if not  api_key or not api_base or not model_name:
        raise ValueError("模型配置信息不全")

    # 2.定义模型实例（llm）(国内的模型都是支持的)
    # llm=ChatOpenAI(model_name=model_name,openai_api_key=api_key,openai_api_base=api_base)
    llm = ChatOpenAI(model_name="Qwen/Qwen3-8B",
                     api_key="sk-bkmcdmgisovhafmphegqojjdaypwnycmfiekqdnnvdeqvjks",
                     openai_api_base="https://api.siliconflow.cn/v1/chat/completions")

    # 3.定义提示词模版对象（PromptTemplate ChatPromptTemplate【聊天提示词模版对象】）
    # 3.1 PromptTemplate或者ChatPromptTemplate对象 有且只有两种方式（①实例化ChatPromptTemplate（） ②调用类方法ChatPromptTemplate.from_messages()）
     # role:AI/Human/System
    chat_prompt_template=ChatPromptTemplate.from_messages([
        ("system","{system_instruction}"),
        ("human","{query}")
    ])

    # 4.定义链（chain）--->通过LCEL语法构建链  "" | ""
    chain= chat_prompt_template | llm

    # 5.执行链（分别执行链上的每一个组件） Runnable(可运行)---invoke()[ 1.提示词模版对象 2.llm实例 3.链 4.工具 Agent]  # 执行模型（给服务端发送请求）

    response=chain.invoke({"system_instruction":system_instruction,"query":query}) # 1.先去调用chat_prompt_template组件的invoke("模版中的变量"):结果：格式化后的模版（变量已经赋值了）  llm.invoke(格式化后的模版（变量已经赋值了）)

    # 6.直接解析模型结果(str)
    return response.content



if __name__ == '__main__':
    result=call_llm(query="当下AI就业环境到底怎么样？",system_instruction="您是一位AI就业分析的市场专家，请客观回答用户询问的就业问题")
    print(result)








