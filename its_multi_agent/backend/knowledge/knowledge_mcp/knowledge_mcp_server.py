import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.ragas_eval import get_latest_rows_file
from services.query_service import QueryService
from services.retrieval_service import RetrievalService


mcp = FastMCP("知识库问答服务")


@lru_cache(maxsize=1)
def get_retrieval_service() -> RetrievalService:
    """延迟初始化检索服务，避免导入服务端时立刻加载大对象。"""
    return RetrievalService()


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    """延迟初始化问答服务，避免工具未被调用时产生额外开销。"""
    return QueryService()


def serialize_documents(documents: list[Any]) -> list[dict[str, Any]]:
    """把 LangChain Document 转成 MCP 更容易消费的普通字典。"""
    serialized = []
    for index, document in enumerate(documents, start=1):
        serialized.append(
            {
                "rank": index,
                "title": document.metadata.get("title", ""),
                "path": document.metadata.get("path", ""),
                "content": document.page_content,
            }
        )
    return serialized


@mcp.tool()
def search_knowledge(query: str, top_k: int = 2) -> str:
    """检索知识库，返回最相关的文档片段。"""
    retrieval_service = get_retrieval_service()
    documents = retrieval_service.retrieval(query)[: max(top_k, 1)]
    return json.dumps(
        {
            "query": query,
            "count": len(documents),
            "documents": serialize_documents(documents),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def ask_knowledge(question: str) -> str:
    """基于知识库直接回答问题，并附带引用到的资料标题。"""
    retrieval_service = get_retrieval_service()
    query_service = get_query_service()
    documents = retrieval_service.retrieval(question)
    answer = query_service.generate_answer(question, documents)
    payload = {
        "question": question,
        "answer": answer,
        "sources": [
            {
                "title": document.metadata.get("title", ""),
                "path": document.metadata.get("path", ""),
            }
            for document in documents
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def latest_evaluation_summary() -> str:
    """返回最近一次评测样本文件的基础信息。"""
    rows_file = get_latest_rows_file()
    rows = json.loads(rows_file.read_text(encoding="utf-8"))
    payload = {
        "rows_file": str(rows_file),
        "case_count": len(rows),
        "sample_questions": [
            row.get("user_input") or row.get("question", "") for row in rows[:3]
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("Knowledge MCP Server 正在启动，默认 SSE 地址为 http://127.0.0.1:9000/sse")
    mcp.run(transport="sse")
