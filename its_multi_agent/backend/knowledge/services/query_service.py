from typing import List

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from config.settings import settings


class QueryService:
    """
    生成答案的服务层。

    RetrievalService 负责“找资料”，
    QueryService 负责“把资料整理成自然语言回答”。
    """

    def __init__(self):
        # ChatOpenAI 是 LangChain 对 OpenAI 兼容接口的封装。
        # 我们这里只是在初始化客户端，真正请求模型是在 invoke() 时发送的。
        self.llm = ChatOpenAI(
            model=settings.MODEL,
            openai_api_key=settings.API_KEY,
            openai_api_base=settings.BASE_URL,
            temperature=0,
        )

    def generate_answer(
        self, user_question: str, retrival_context: List[Document]
    ) -> str:
        """
        把检索到的上下文交给大模型生成最终答案。
        """
        if not retrival_context:
            return "未检索到任何相关文档，无法提供回复"

        retrieval_context_text = "\n\n".join(
            [
                f"资料{index + 1}:{document}"
                for index, document in enumerate(retrival_context)
            ]
        )

        prompt = f"""
你是一位经验丰富的高级技术支持专家。请基于下方的【参考资料】回答【用户问题】。

【参考资料】：
```
{retrieval_context_text}
```

【用户问题】：
```
{user_question}
```

【回答要求】：
1. 严格基于【参考资料】回答，不要编造资料中没有的信息。
2. 如果资料不足以回答，请直接说“当前知识库中暂时没有找到该问题的解决方案。”
3. 除非问题明确指定了品牌或型号，否则尽量泛化表述，不强行带入具体型号。
4. 如果答案是操作步骤，请使用 1. 2. 3. 的有序列表。
5. 在答案最后列出你参考了哪些资料编号。
"""

        llm_response = self.llm.invoke(prompt)
        return llm_response.content
