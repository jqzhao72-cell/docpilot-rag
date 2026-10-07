"""End-to-end Hybrid Retrieval, reranking, and DeepSeek answer pipeline."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Mapping

from rag.hybrid_retrieval import HybridRetriever
from rag.llm import DeepSeekLLM
from rag.prompt import build_prompt
from rag.reranker import Reranker, second_stage_rank_fusion


DEFAULT_CANDIDATE_TOP_K = 20
DEFAULT_FINAL_TOP_K = 5
DEFAULT_REFERENCE_RANK_PENALTY = 4


def _page_label(result: Mapping[str, Any]) -> str:
    page_start = result.get("page_start")
    page_end = result.get("page_end")
    if page_start is None and page_end is None:
        return "unknown"
    if page_end is None or page_start == page_end:
        return str(page_start)
    if page_start is None:
        return str(page_end)
    return f"{page_start}-{page_end}"


def build_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build citation metadata in the same order used by prompt contexts."""
    return [
        {
            "index": index,
            "id": result.get("id"),
            "source": result.get("source"),
            "page": _page_label(result),
            "page_start": result.get("page_start"),
            "page_end": result.get("page_end"),
            "section": result.get("section"),
            "chunk_type": result.get("chunk_type"),
        }
        for index, result in enumerate(results, start=1)
    ]


class PaperRAGPipeline:
    """Run Query -> Hybrid -> Reranker -> penalty fusion -> Prompt -> DeepSeek."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever | None = None,
        reranker: Reranker | None = None,
        llm: DeepSeekLLM | None = None,
        candidate_top_k: int = DEFAULT_CANDIDATE_TOP_K,
        final_top_k: int = DEFAULT_FINAL_TOP_K,
        reference_rank_penalty: int = DEFAULT_REFERENCE_RANK_PENALTY,
    ) -> None:
        for name, value in (
            ("candidate_top_k", candidate_top_k),
            ("final_top_k", final_top_k),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(reference_rank_penalty, bool)
            or not isinstance(reference_rank_penalty, int)
            or reference_rank_penalty < 0
        ):
            raise ValueError("reference_rank_penalty must be a non-negative integer")

        self.hybrid_retriever = hybrid_retriever or HybridRetriever()
        self.reranker = reranker or Reranker()
        self.llm = llm or DeepSeekLLM()
        self.candidate_top_k = candidate_top_k
        self.final_top_k = final_top_k
        self.reference_rank_penalty = reference_rank_penalty

    def answer(
        self,
        query: str,
        metadata_filter: Mapping[str, Any] | None = None,
        history_text: str = "",
    ) -> dict[str, Any]:
        """Answer a query and return grounded sources, final results, and timings."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        query = query.strip()
        total_started = perf_counter()

        retrieval_started = perf_counter()
        hybrid_results = self.hybrid_retriever.search(
            query,
            top_k=self.candidate_top_k,
            metadata_filter=metadata_filter,
        )
        retrieval_ms = (perf_counter() - retrieval_started) * 1000

        reranker_started = perf_counter()
        reranked_results = self.reranker.rerank(
            query,
            hybrid_results,
            top_k=self.candidate_top_k,
        )
        reranker_ms = (perf_counter() - reranker_started) * 1000

        final_results = second_stage_rank_fusion(
            hybrid_results,
            reranked_results,
            k=60,
            top_k=self.final_top_k,
            query=query,
            reference_rank_penalty=self.reference_rank_penalty,
        )
        prompt = build_prompt(query, final_results, history_text=history_text)

        llm_started = perf_counter()
        answer = self.llm.generate(prompt)
        llm_ms = (perf_counter() - llm_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000

        return {
            "answer": answer,
            "sources": build_sources(final_results),
            "retrieval_results": final_results,
            "timings": {
                "retrieval_ms": retrieval_ms,
                "reranker_ms": reranker_ms,
                "deepseek_api_ms": llm_ms,
                "total_ms": total_ms,
            },
        }
