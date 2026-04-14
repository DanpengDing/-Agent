import logging
import re
from typing import Any, Dict, List, Optional

import jieba
from langchain_core.documents import Document
from sklearn.metrics.pairwise import cosine_similarity

from config.settings import settings
from repositories.vector_store_repository import VectorStoreRepository
from services.ingestion.ingestion_processor import IngestionProcessor
from utils.markdown_utils import MarkDownUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetrievalService:
    """
    知识库检索服务。

    当前采用“两路召回 + 二次重排”的思路：
    1. 向量召回：擅长语义相近但字面不完全相同的问题。
    2. 标题召回：擅长命中知识库里非常明确的标题。
    3. 合并去重后再统一重排，避免只靠单一路径导致漏召回。
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreRepository] = None,
        crawl_output_dir: Optional[str] = None,
    ):
        self.chroma_vector = vector_store or VectorStoreRepository()
        self.spliter = IngestionProcessor(vector_store=self.chroma_vector)
        self.crawl_output_dir = crawl_output_dir or settings.CRAWL_OUTPUT_DIR

    def rough_ranking(
        self, user_query: str, mds_metadata: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        标题粗排。

        先用非常便宜的字面特征把候选文档缩小到 50 篇左右，
        这样后面再做 embedding 精排时成本更可控。
        """
        if not user_query:
            return []

        rough_word_weight = 0.7
        for md_metadata in mds_metadata:
            md_metadata_title = md_metadata["title"]
            if not md_metadata_title or not md_metadata_title.strip():
                continue

            user_query_char = set(user_query)
            md_title_char = set(md_metadata_title)
            unique_char = user_query_char | md_title_char
            char_score = (
                len(user_query_char & md_title_char) / len(unique_char)
                if unique_char
                else 0
            )

            user_query_word = set(jieba.lcut(user_query))
            md_title_word = set(jieba.lcut(md_metadata_title))
            unique_word = user_query_word | md_title_word
            word_score = (
                len(user_query_word & md_title_word) / len(unique_word)
                if unique_word
                else 0
            )

            md_metadata["roughing_score"] = float(
                word_score * rough_word_weight + char_score * (1 - rough_word_weight)
            )

        return sorted(
            mds_metadata,
            key=lambda item: item.get("roughing_score", 0.0),
            reverse=True,
        )[: settings.TOP_ROUGH]

    def fine_ranking(
        self, user_query: str, rough_mds_metadata: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        标题精排。

        这里才调用 embedding，把“问题”和“标题”转成向量后做余弦相似度。
        """
        if not rough_mds_metadata:
            return []

        query_embedding = self.chroma_vector.embedd_document(user_query)
        roughing_title = [md_metadata["title"] for md_metadata in rough_mds_metadata]
        roughing_title_embeddings = self.chroma_vector.embedd_documents(roughing_title)
        similarity = cosine_similarity([query_embedding], roughing_title_embeddings).flatten()

        rough_height = 0.3
        sim_height = 0.7
        for index, md_metadata in enumerate(rough_mds_metadata):
            sim = max(float(similarity[index]), 0.0)
            roughing_score = md_metadata.get("roughing_score", 0.0)
            final_score = roughing_score * rough_height + sim * sim_height

            md_metadata["sim_score"] = sim
            md_metadata["final_score"] = final_score

        return sorted(
            rough_mds_metadata,
            key=lambda item: item["final_score"],
            reverse=True,
        )[: settings.TOP_FINAL]

    def retrieval(self, user_question: str) -> List[Document]:
        """
        对外暴露的统一检索入口。

        FastAPI 路由、测评脚本、工具调用，最终都会走到这里。
        """
        based_vector_candidates = self._search_based_vector(user_question)
        based_title_candidates = self._search_based_title(user_question)
        total_candidates = based_vector_candidates + based_title_candidates
        unique_candidates = self._deduplicate(total_candidates)
        return self._reranking(unique_candidates, user_question)

    def _search_based_vector(self, user_question: str) -> List[Document]:
        """第一路：向量检索。"""
        documents_with_score = self.chroma_vector.search_similarity_with_score(user_question)
        return [document for document, _ in documents_with_score]

    def _search_based_title(self, user_query: str) -> List[Document]:
        """第二路：基于标题的检索。"""
        mds_metadata = MarkDownUtils.collect_md_metadata(self.crawl_output_dir)
        rough_mds_metadata = self.rough_ranking(user_query, mds_metadata)
        fine_mds_metadata = self.fine_ranking(user_query, rough_mds_metadata)

        based_title_candidates = []
        for fine_md_metadata in fine_mds_metadata:
            try:
                with open(fine_md_metadata["path"], "r", encoding="utf-8") as file:
                    content = file.read().strip()

                if len(content) < 3000:
                    based_title_candidates.append(
                        Document(
                            page_content=content,
                            metadata={
                                "path": fine_md_metadata["path"],
                                "title": fine_md_metadata["title"],
                            },
                        )
                    )
                else:
                    doc_chunks = self._deal_long_title_content(
                        content, fine_md_metadata, user_query
                    )
                    based_title_candidates.extend(doc_chunks)
            except Exception as exc:
                logger.error("打开文件失败: %s", exc)
                return []

        return based_title_candidates

    def _deduplicate(self, total_candidates: List[Document]) -> List[Document]:
        """
        合并两路召回结果后去重。

        这里不是按路径去重，而是按“标题 + 内容前 100 个字符”做粗粒度去重，
        目的是把内容几乎相同的重复块压掉。
        """
        if not total_candidates:
            return []

        seen = set()
        unique_candidates = []

        for document in total_candidates:
            clean_content = re.sub(
                r"^文档来源:.*?(?=(\n|#))",
                "",
                document.page_content,
                flags=re.DOTALL,
            ).strip()
            key = (document.metadata["title"], clean_content[:100])
            if key not in seen:
                seen.add(key)
                unique_candidates.append(document)

        return unique_candidates

    def _reranking(
        self, unique_candidates: List[Document], user_question: str
    ) -> List[Document]:
        """
        对合并后的候选文档再统一打一遍分。

        长文档切出来的块已经在 `_deal_long_title_content()` 里算过相似度了，
        这里直接复用；其它文档则在这里补算。
        """
        if not unique_candidates:
            return []

        need_embedding_docs = []
        need_embedding_candidates_indices = []
        score_doc = []

        for candidate_index, unique_candidate in enumerate(unique_candidates):
            if (
                "chunk_index" in unique_candidate.metadata
                and "similarity" in unique_candidate.metadata
            ):
                score_doc.append((unique_candidate, unique_candidate.metadata["similarity"]))
            else:
                need_embedding_docs.append(unique_candidate)
                need_embedding_candidates_indices.append(candidate_index)

        if need_embedding_docs:
            query_embedding = self.chroma_vector.embedd_document(user_question)
            embedding_docs_content = [
                "文档来源:" + doc.metadata["title"] + doc.page_content
                for doc in need_embedding_docs
            ]
            doc_embeddings = self.chroma_vector.embedd_documents(embedding_docs_content)
            similarity = cosine_similarity([query_embedding], doc_embeddings).flatten()

            for idx, candidate_index in enumerate(need_embedding_candidates_indices):
                score_doc.append((unique_candidates[candidate_index], float(similarity[idx])))

        sorted_docs = sorted(score_doc, key=lambda item: item[1], reverse=True)
        return [doc for doc, _ in sorted_docs[:2]]

    def _deal_long_title_content(
        self,
        content: str,
        fine_md_metadata: Dict[str, Any],
        user_query: str,
    ) -> List[Document]:
        """
        长文档处理逻辑。

        标题命中了，不代表整篇长文都和问题相关。
        所以要把长文再切块，找到其中最相关的几个块返回给后面的生成模型。
        """
        chunks = self.spliter.document_spliter.split_text(content)
        doc_chunks_title = fine_md_metadata["title"]
        doc_chunks_inject_title = [f"文档来源:{doc_chunks_title}\n{chunk}" for chunk in chunks]

        query_embedding = self.chroma_vector.embedd_document(user_query)
        doc_chunk_embeddings = self.chroma_vector.embedd_documents(doc_chunks_inject_title)
        doc_chunks_similarity = cosine_similarity(
            [query_embedding], doc_chunk_embeddings
        ).flatten()
        top_doc_chunks_indices = doc_chunks_similarity.argsort()[-3:][::-1]

        docs = []
        for chunk_idx in top_doc_chunks_indices:
            docs.append(
                Document(
                    page_content=doc_chunks_inject_title[int(chunk_idx)],
                    metadata={
                        "path": fine_md_metadata["path"],
                        "title": fine_md_metadata["title"],
                        # 这里的 key 需要和 _reranking() 的判断保持一致。
                        "chunk_index": int(chunk_idx),
                        "similarity": float(doc_chunks_similarity[chunk_idx]),
                    },
                )
            )

        return docs


if __name__ == "__main__":
    retrieval_service = RetrievalService()
    result = retrieval_service.retrieval("如何使用U盘安装Windows 7操作系统")
    for item in result:
        print(item)
