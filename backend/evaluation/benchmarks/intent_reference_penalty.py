"""Compare intent-aware Reference rank penalties after second-stage RRF."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.hybrid_retrieval import HybridRetriever
from rag.reranker import Reranker, detect_query_intent, second_stage_rank_fusion


KNOWLEDGE_QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)
CITATION_QUERIES = (
    "papers cited for AKR1C3",
    "references about tumor immune microenvironment",
)
PENALTIES = (0, 2, 4, 6)


def result_ids(results: list[dict]) -> tuple[str, ...]:
    return tuple(str(item["id"]) for item in results)


def print_top_five(penalty: int, results: list[dict]) -> None:
    references = sum(bool(item["is_reference"]) for item in results)
    print(f"  penalty={penalty} Top-5 (references={references})")
    for rank, item in enumerate(results, start=1):
        print(
            f"    {rank}. id={item['id']} ref={item['is_reference']} "
            f"rrf={item['rrf_rank']}->{item['effective_rrf_rank']} "
            f"rerank={item.get('rerank_rank', '-')}->"
            f"{item.get('effective_rerank_rank', '-')} "
            f"applied={item['applied_reference_rank_penalty']} "
            f"section={item.get('section')!r}"
        )


def main() -> int:
    hybrid = HybridRetriever()
    reranker = Reranker()
    timings: list[float] = []
    knowledge_reference_counts = {penalty: 0 for penalty in PENALTIES}
    citation_reference_counts = {penalty: 0 for penalty in PENALTIES}
    citation_results_unchanged = True

    print(f"Model: {reranker.model_name}")
    print(f"Default batch size: {reranker.batch_size}")

    for query in KNOWLEDGE_QUERIES + CITATION_QUERIES:
        intent = detect_query_intent(query)
        hybrid_results = hybrid.search_with_components(
            query, top_k=20, dense_top_n=20, bm25_top_n=20
        )["hybrid"]
        started = perf_counter()
        reranked_results = reranker.rerank(query, hybrid_results, top_k=20)
        elapsed_ms = (perf_counter() - started) * 1000
        timings.append(elapsed_ms)

        comparisons: dict[int, list[dict]] = {}
        for penalty in PENALTIES:
            results = second_stage_rank_fusion(
                hybrid_results,
                reranked_results,
                k=60,
                top_k=5,
                query=query,
                reference_rank_penalty=penalty,
            )
            comparisons[penalty] = results
            target_counts = (
                citation_reference_counts
                if intent == "citation"
                else knowledge_reference_counts
            )
            target_counts[penalty] += sum(
                bool(item["is_reference"]) for item in results
            )

        print("\n" + "=" * 110)
        print(f"Query: {query}")
        print(f"Intent: {intent}; rerank latency: {elapsed_ms:.2f} ms")
        for penalty in PENALTIES:
            print_top_five(penalty, comparisons[penalty])

        if intent == "citation":
            baseline_ids = result_ids(comparisons[0])
            unchanged = all(
                result_ids(comparisons[penalty]) == baseline_ids
                and all(
                    item["applied_reference_rank_penalty"] == 0
                    for item in comparisons[penalty]
                )
                for penalty in PENALTIES[1:]
            )
            citation_results_unchanged &= unchanged
            print(f"  Citation penalty bypass verified: {unchanged}")

    print("\n" + "=" * 110)
    print(f"Average rerank latency (7 queries): {sum(timings) / len(timings):.2f} ms")
    print(
        "Knowledge-query Reference counts across five Top-5 lists: "
        + ", ".join(
            f"penalty={penalty}: {knowledge_reference_counts[penalty]}/25"
            for penalty in PENALTIES
        )
    )
    print(
        "Citation-query Reference counts across two Top-5 lists: "
        + ", ".join(
            f"penalty={penalty}: {citation_reference_counts[penalty]}/10"
            for penalty in PENALTIES
        )
    )
    print(f"Citation-query Top-5 unchanged: {citation_results_unchanged}")
    return 0 if citation_results_unchanged else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
