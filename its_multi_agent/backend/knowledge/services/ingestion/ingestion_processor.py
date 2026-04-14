import logging
import os.path
from typing import Optional

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_text_splitters import RecursiveCharacterTextSplitter

from repositories.vector_store_repository import VectorStoreRepository
from utils.markdown_utils import MarkDownUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionProcessor:
    """
    文档入库服务。

    RAG 的“入库”不是简单把文件路径记下来，而是：
    1. 读取 Markdown 内容；
    2. 按语义尽量完整地切块；
    3. 给每个块补上标题等上下文；
    4. 生成向量并写入 Chroma。
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreRepository] = None,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
    ):
        self.vector_store = vector_store or VectorStoreRepository()

        # LangChain 的切分器会自动按照 separators 的优先级切文本，
        # 这里不是我们手写循环切字符串，而是框架在内部帮我们做切分。
        self.document_spliter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n## ",
                "\n**",
                "\n\n",
                "\n",
                " ",
                "",
            ],
        )

    def ingest_file(self, md_path: str) -> int:
        """
        单文件入库入口。

        返回值是本次真正写进向量库的文档块数量，便于前端或脚本展示进度。
        """
        try:
            text_loader = TextLoader(file_path=md_path, encoding="utf-8")
            documents = text_loader.load()
        except Exception as exc:
            logger.error("文件加载失败: %s, 原因: %s", md_path, exc)
            raise Exception(f"文件 {md_path} 加载失败: {exc}") from exc

        for doc in documents:
            doc.metadata["title"] = MarkDownUtils.extract_title(md_path)

        final_document_chunks = []
        for doc in documents:
            # 短文档不切块，避免把本来就不长的步骤说明切碎。
            if len(doc.page_content) < 3000:
                final_document_chunks.append(doc)
                continue

            # 这里只切当前 doc。
            # 旧代码误把整个 documents 列表反复切分，会导致重复块。
            document_chunks_list = self.document_spliter.split_documents([doc])
            for document_chunk in document_chunks_list:
                source_path = document_chunk.metadata["source"]
                title = os.path.basename(source_path)

                # 给每个块补上来源标题，后续召回后模型更容易知道这段内容属于哪篇文档。
                document_chunk.page_content = (
                    f"文档来源:{title}\n{document_chunk.page_content}"
                )

            final_document_chunks.extend(document_chunks_list)

        clean_documents_chunks = filter_complex_metadata(final_document_chunks)
        valid_documents_chunks = [
            document
            for document in clean_documents_chunks
            if document.page_content.strip()
        ]

        if not valid_documents_chunks:
            logger.error("切分后的文档块没有任何有效内容")
            return 0

        return self.vector_store.add_documents(valid_documents_chunks)


if __name__ == "__main__":
    ingest_processor = IngestionProcessor()
    ingest_processor.ingest_file(
        "C:\\Users\\Administrator\\Desktop\\0430-联想手机K900常见问题汇总.md"
    )
