"""Compare Hybrid, pure BGE reranking, and second-stage rank fusion."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.hybrid_retrieval import HybridRetriever
from rag.reranker import Reranker, is_reference_candidate, second_stage_rank_fusion


QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)


def print_ranking(label: str, results: list[dict]) -> None:
    print(f"\n{label} Top-5")
    for rank, item in enumerate(results[:5], start=1):
        print(
            f"  {rank}. id={item['id']} reference={is_reference_candidate(item)} "
            f"rrf_rank={item.get('rrf_rank', rank)} "
            f"rerank_rank={item.get('rerank_rank', '-')} "
            f"source={item.get('source')} section={item.get('section')!r}"
        )
        print(f"     {' '.join((item.get('text') or '').split())[:220]}")


def main() -> int:
    hybrid = HybridRetriever()
    reranker = Reranker()
    timings = []
    reference_counts = {"hybrid": 0, "pure": 0, "fused": 0}
    print(f"Model: {reranker.model_name}")
    print(f"Default batch size: {reranker.batch_size}")

    for query in QUERIES:
        hybrid_results = hybrid.search_with_components(
            query, top_k=20, dense_top_n=20, bm25_top_n=20
        )["hybrid"]
        started = perf_counter()
        pure_results = reranker.rerank(query, hybrid_results, top_k=20)
        elapsed_ms = (perf_counter() - started) * 1000
        timings.append(elapsed_ms)
        fused_results = second_stage_rank_fusion(
            hybrid_results, pure_results, k=60, top_k=5
        )

        reference_counts["hybrid"] += sum(
            is_reference_candidate(item) for item in hybrid_results[:5]
        )
        reference_counts["pure"] += sum(
            item["is_reference"] for item in pure_results[:5]
        )
        reference_counts["fused"] += sum(
            item["is_reference"] for item in fused_results
        )

        print("\n" + "=" * 110)
        print(f"Query: {query}")
        print(f"Rerank latency: {elapsed_ms:.2f} ms")
        print_ranking("Hybrid RRF", hybrid_results)
        print_ranking("Pure Reranker", pure_results)
        print_ranking("Second-stage RRF", fused_results)

    print("\n" + "=" * 110)
    print(f"Average rerank latency: {sum(timings) / len(timings):.2f} ms")
    print(
        "Reference counts across five Top-5 lists: "
        f"Hybrid={reference_counts['hybrid']}/25, "
        f"Pure={reference_counts['pure']}/25, "
        f"Fused={reference_counts['fused']}/25"
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
