from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QueryRewriteResult:
    original_query: str
    rewritten_query: str


class QueryRewriteService:
    async def rewrite(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> QueryRewriteResult:
        return QueryRewriteResult(original_query=query, rewritten_query=query)

    def build_process_message(self, result: QueryRewriteResult) -> str:
        return f"[\u67e5\u8be2\u5206\u6790] \u539f\u59cb\u95ee\u9898: {result.original_query}\n"


query_rewrite_service = QueryRewriteService()
