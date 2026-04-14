import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
from datasets import Dataset
from langchain_openai import OpenAIEmbeddings
from openai import AsyncOpenAI
from ragas import evaluate
from ragas.llms.base import llm_factory
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
from tqdm import tqdm

from config.settings import settings
from evaluation.eval_cases import EVAL_CASES
from repositories.vector_store_repository import VectorStoreRepository
from services.ingestion.ingestion_processor import IngestionProcessor
from services.query_service import QueryService
from services.retrieval_service import RetrievalService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于 ragas 的知识库真实测评脚本")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="报告输出目录，默认写到 backend/knowledge/eval_outputs/<时间戳>",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="只索引前 N 篇文档，默认索引 crawl 目录下全部 Markdown",
    )
    parser.add_argument(
        "--keep-index",
        action="store_true",
        help="保留本次测评构建的临时 Chroma 索引目录",
    )
    return parser.parse_args()


def build_eval_index(index_dir: Path, markdown_files: List[Path]) -> dict:
    vector_store = VectorStoreRepository(
        persist_directory=str(index_dir),
        collection_name=f"its-ragas-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    )
    ingestion_processor = IngestionProcessor(vector_store=vector_store)

    success = 0
    fail = 0
    chunks_added = 0

    for markdown_file in tqdm(markdown_files, desc="构建测评索引"):
        try:
            chunks_added += ingestion_processor.ingest_file(str(markdown_file))
            success += 1
        except Exception as exc:
            fail += 1
            print(f"[WARN] 入库失败: {markdown_file.name} -> {exc}")

    return {
        "vector_store": vector_store,
        "success_docs": success,
        "fail_docs": fail,
        "chunks_added": chunks_added,
    }


def run_pipeline_cases(retrieval_service: RetrievalService, query_service: QueryService) -> list:
    rows = []
    for case in tqdm(EVAL_CASES, desc="执行问答样例"):
        docs = retrieval_service.retrieval(case["question"])
        answer = query_service.generate_answer(case["question"], docs)
        rows.append(
            {
                "source_file": case["source_file"],
                "user_input": case["question"],
                "reference": case["reference"],
                "response": answer,
                "retrieved_contexts": [doc.page_content for doc in docs],
                "retrieved_titles": " | ".join(
                    [doc.metadata.get("title", "") for doc in docs]
                ),
            }
        )
    return rows


def evaluate_rows(rows: list):
    ragas_llm = llm_factory(
        settings.MODEL,
        client=AsyncOpenAI(api_key=settings.API_KEY, base_url=settings.BASE_URL),
    )
    # 旧版 AnswerRelevancy 指标要求 embeddings 对象带 embed_query()/embed_documents()，
    # 直接复用项目当前使用的 LangChain Embeddings 兼容性更稳定。
    ragas_embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.API_KEY,
        openai_api_base=settings.BASE_URL,
    )

    metrics = [
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings, strictness=1),
        ContextRecall(llm=ragas_llm),
        ContextPrecision(llm=ragas_llm),
    ]

    dataset = Dataset.from_list(rows)
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        show_progress=True,
        raise_exceptions=True,
    )
    return result, result.to_pandas()


def write_report(
    output_dir: Path,
    detail_df: pd.DataFrame,
    metadata: dict,
) -> tuple[Path, Path, Path]:
    detail_csv_path = output_dir / "ragas_detail.csv"
    detail_json_path = output_dir / "ragas_detail.json"
    report_md_path = output_dir / "ragas_report.md"

    detail_df.to_csv(detail_csv_path, index=False, encoding="utf-8-sig")
    detail_df.to_json(detail_json_path, orient="records", force_ascii=False, indent=2)

    metric_columns = [
        "faithfulness",
        "answer_relevancy",
        "context_recall",
        "context_precision",
    ]
    summary = detail_df[metric_columns].mean(numeric_only=True)

    lines = [
        "# RAGAS 测评报告",
        "",
        f"- 生成时间: {metadata['generated_at']}",
        f"- 文档目录: `{metadata['crawl_dir']}`",
        f"- 参与索引文档数: {metadata['indexed_doc_count']}",
        f"- 入库成功文档数: {metadata['success_docs']}",
        f"- 入库失败文档数: {metadata['fail_docs']}",
        f"- 写入向量块数: {metadata['chunks_added']}",
        f"- 测评样例数: {metadata['case_count']}",
        "",
        "## 总体得分",
        "",
        "| 指标 | 分数 |",
        "| --- | ---: |",
        f"| faithfulness | {summary['faithfulness']:.4f} |",
        f"| answer_relevancy | {summary['answer_relevancy']:.4f} |",
        f"| context_recall | {summary['context_recall']:.4f} |",
        f"| context_precision | {summary['context_precision']:.4f} |",
        "",
        "## 逐题结果",
        "",
        "| 来源文档 | 问题 | 检索到的标题 | faithfulness | answer_relevancy | context_recall | context_precision |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]

    for _, row in detail_df.iterrows():
        question = str(row["user_input"]).replace("\n", " ")
        titles = str(row.get("retrieved_titles", "")).replace("\n", " ")
        lines.append(
            "| {source_file} | {question} | {titles} | {faithfulness:.4f} | {answer_relevancy:.4f} | {context_recall:.4f} | {context_precision:.4f} |".format(
                source_file=row["source_file"],
                question=question,
                titles=titles,
                faithfulness=float(row["faithfulness"]),
                answer_relevancy=float(row["answer_relevancy"]),
                context_recall=float(row["context_recall"]),
                context_precision=float(row["context_precision"]),
            )
        )

    report_md_path.write_text("\n".join(lines), encoding="utf-8")
    return report_md_path, detail_csv_path, detail_json_path


def main():
    args = parse_args()
    knowledge_root = Path(__file__).resolve().parents[1]
    crawl_dir = Path(settings.CRAWL_OUTPUT_DIR)
    markdown_files = sorted(crawl_dir.glob("*.md"))
    if args.max_docs:
        markdown_files = markdown_files[: args.max_docs]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else knowledge_root / "eval_outputs" / timestamp
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    index_dir = output_dir / "chroma_index"

    index_result = build_eval_index(index_dir, markdown_files)
    vector_store = index_result["vector_store"]

    retrieval_service = RetrievalService(
        vector_store=vector_store,
        crawl_output_dir=str(crawl_dir),
    )
    query_service = QueryService()

    rows = run_pipeline_cases(retrieval_service, query_service)
    result, detail_df = evaluate_rows(rows)

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crawl_dir": str(crawl_dir),
        "indexed_doc_count": len(markdown_files),
        "success_docs": index_result["success_docs"],
        "fail_docs": index_result["fail_docs"],
        "chunks_added": index_result["chunks_added"],
        "case_count": len(EVAL_CASES),
        "ragas_result_repr": str(result),
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_md_path, detail_csv_path, detail_json_path = write_report(
        output_dir, detail_df, metadata
    )

    if not args.keep_index:
        shutil.rmtree(index_dir, ignore_errors=True)

    print("测评完成")
    print(f"报告: {report_md_path}")
    print(f"明细 CSV: {detail_csv_path}")
    print(f"明细 JSON: {detail_json_path}")


if __name__ == "__main__":
    main()
