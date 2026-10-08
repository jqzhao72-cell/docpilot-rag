"""Compare RRF Top-5 with BGE-reranked Top-5 for the paper corpus."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.hybrid_retrieval import HybridRetriever
from rag.reranker import Reranker


QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)


def compact(text: str, limit: int = 150) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_rrf(results: list[dict]) -> None:
    print("\nRRF Top-5")
    for rank, item in enumerate(results[:5], start=1):
        print(
            f"  {rank}. id={item['id']} rrf={item['rrf_score']:.6f} "
            f"type={item['chunk_type']} source={item['source']} "
            f"page={item['page_start']}-{item['page_end']}"
        )
        print(f"     {compact(item['text'])}")


def print_final(results: list[dict]) -> None:
    print("\nReranker Top-5")
    for item in results:
        print(
            f"  {item['final_rank']}. id={item['id']} rerank={item['rerank_score']:.6f} "
            f"rrf_rank={item['rrf_rank']} rank_change={item['rank_change']:+d} "
            f"type={item['chunk_type']} source={item['source']} "
            f"page={item['page_start']}-{item['page_end']}"
        )
        print(f"     {compact(item['text'])}")


def main() -> int:
    hybrid = HybridRetriever()
    reranker = Reranker(batch_size=8)
    timings = []
    print(f"Reranker model: {reranker.model_name}")
    print(f"Model load time: {reranker.model_load_time_ms:.2f} ms")

    for query in QUERIES:
        components = hybrid.search_with_components(
            query, top_k=20, dense_top_n=20, bm25_top_n=20
        )
        candidates = components["hybrid"]
        started = perf_counter()
        final_results = reranker.rerank(query, candidates, top_k=5)
        elapsed_ms = (perf_counter() - started) * 1000
        timings.append(elapsed_ms)

        print("\n" + "=" * 100)
        print(f"Query: {query}")
        print(f"Rerank latency: {elapsed_ms:.2f} ms")
        print_rrf(candidates)
        print_final(final_results)

    print(f"\nAverage rerank latency: {sum(timings) / len(timings):.2f} ms")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
