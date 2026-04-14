import logging
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai.embeddings import OpenAIEmbeddings

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStoreRepository:
    """
    向量库访问层。

    这里把两件事封装在一起：
    1. 创建 Embedding 模型客户端。
    2. 创建/连接 Chroma 向量库。

    业务层只需要关心“存文档”和“查相似文档”，
    不需要知道底层到底是怎么和 Embedding API、Chroma 交互的。
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "its-knowledge",
        embedding_model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        默认读取项目配置。

        之所以允许外部传参，是为了让测评脚本可以单独创建一份临时知识库，
        避免直接污染现有业务库。
        """
        self.embedding = OpenAIEmbeddings(
            model=embedding_model or settings.EMBEDDING_MODEL,
            openai_api_key=api_key or settings.API_KEY,
            openai_api_base=base_url or settings.BASE_URL,
        )

        self.vector_database = Chroma(
            persist_directory=persist_directory or settings.VECTOR_STORE_PATH,
            collection_name=collection_name,
            embedding_function=self.embedding,
        )

    def add_documents(self, documents: List[Document], batch_size: int = 16) -> int:
        """
        分批写入文档块。

        Chroma 支持一次写很多文档，但分批可以减少单次请求体积，
        出问题时也更容易定位是哪一批失败。
        """
        total_documents_chunks = len(documents)
        documents_chunks_added = 0

        try:
            for index in range(0, total_documents_chunks, batch_size):
                batch = documents[index : index + batch_size]
                self.vector_database.add_documents(batch)
                documents_chunks_added += len(batch)
                logger.info(
                    "成功将文档块保存到向量库: %s/%s",
                    documents_chunks_added,
                    total_documents_chunks,
                )

            return documents_chunks_added
        except Exception as exc:
            logger.error("文档块写入向量库失败: %s", exc)
            raise

    def embedd_document(self, text: str) -> List[float]:
        """把单条文本转成向量。"""
        return self.embedding.embed_query(text)

    def embedd_documents(self, texts: List[str]) -> List[List[float]]:
        """把多条文本批量转成向量。"""
        return self.embedding.embed_documents(texts)

    def search_similarity_with_score(
        self, user_question: str, top_k: int = 5
    ) -> List[tuple[Document, float]]:
        """
        返回 Chroma 的相似度检索结果。

        注意：
        Chroma 这里返回的是“距离分数”，不是已经归一化好的相似度分数。
        后面的业务层会再做一次统一重排。
        """
        return self.vector_database.similarity_search_with_score(user_question, top_k)
