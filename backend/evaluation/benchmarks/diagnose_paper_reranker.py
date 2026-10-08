"""Diagnose BGE reranking inputs, metadata context, references, and batch size."""

from __future__ import annotations

import re
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
BATCH_SIZES = (4, 8, 16)
NUMBERED_REFERENCE = re.compile(r"^\s*\d{1,3}\.(?:\s|$)")


def is_reference_chunk(item: dict) -> bool:
    """Identify explicit or parser-shaped bibliography chunks for statistics."""
    section = str(item.get("section") or "").strip()
    subsection = str(item.get("subsection") or "").strip()
    labels = f"{section} {subsection}".lower()
    return (
        "references" in labels
        or "bibliography" in labels
        or bool(NUMBERED_REFERENCE.match(section))
    )


def token_length(reranker: Reranker, text: str) -> int:
    encoded = reranker.model.tokenizer(
        text,
        add_special_tokens=True,
        truncation=False,
    )
    return len(encoded["input_ids"])


def top_ids(results: list[dict], limit: int = 5) -> tuple[str, ...]:
    return tuple(item["id"] for item in results[:limit])


def timed_rerank(
    reranker: Reranker,
    query: str,
    candidates: list[dict],
    batch_size: int,
    input_mode: str,
) -> tuple[list[dict], float]:
    started = perf_counter()
    results = reranker.rerank(
        query,
        candidates,
        top_k=len(candidates),
        batch_size=batch_size,
        input_mode=input_mode,
    )
    return results, (perf_counter() - started) * 1000


def print_diagnostics(
    reranker: Reranker,
    candidates: list[dict],
    text_results: list[dict],
) -> None:
    by_id = {item["id"]: item for item in text_results}
    print("\nText-only: RRF Top-20 before/after diagnostics")
    for rrf_rank, candidate in enumerate(candidates, start=1):
        result = by_id[candidate["id"]]
        text = candidate.get("text") or ""
        preview = " ".join(text.split())[:300]
        print(
            f"  id={candidate['id']} rrf_rank={rrf_rank} "
            f"final_rank={result['final_rank']} "
            f"rank_change={result['rank_change']:+d} "
            f"rerank_score={result['rerank_score']:.6f} "
            f"source={candidate.get('source')} "
            f"section={candidate.get('section')!r} "
            f"chunk_type={candidate.get('chunk_type')} "
            f"chars={len(text)} tokens={token_length(reranker, text)} "
            f"reference={is_reference_chunk(candidate)}"
        )
        print(f"     {preview}")


def main() -> int:
    hybrid = HybridRetriever()
    reranker = Reranker(batch_size=8)
    print(f"Model: {reranker.model_name}")
    print(f"Model load time: {reranker.model_load_time_ms:.2f} ms")

    timings = {batch_size: [] for batch_size in BATCH_SIZES}
    top5_by_batch = {batch_size: [] for batch_size in BATCH_SIZES}
    reference_totals = {"top20": 0, "text_top5": 0, "structured_top5": 0}

    for query in QUERIES:
        candidates = hybrid.search_with_components(
            query, top_k=20, dense_top_n=20, bm25_top_n=20
        )["hybrid"]

        text_runs = {}
        for batch_size in BATCH_SIZES:
            results, elapsed_ms = timed_rerank(
                reranker, query, candidates, batch_size, "text"
            )
            text_runs[batch_size] = results
            timings[batch_size].append(elapsed_ms)
            top5_by_batch[batch_size].append(top_ids(results))

        structured_results, structured_ms = timed_rerank(
            reranker, query, candidates, 8, "structured"
        )
        text_results = text_runs[8]

        reference_totals["top20"] += sum(is_reference_chunk(x) for x in candidates)
        reference_totals["text_top5"] += sum(
            is_reference_chunk(x) for x in text_results[:5]
        )
        reference_totals["structured_top5"] += sum(
            is_reference_chunk(x) for x in structured_results[:5]
        )

        print("\n" + "=" * 120)
        print(f"Query: {query}")
        print_diagnostics(reranker, candidates, text_results)
        print("\nTop-5 comparison")
        print(f"  A text-only:  {top_ids(text_results)}")
        print(f"  B structured: {top_ids(structured_results)}")
        print(f"  Structured batch=8 latency: {structured_ms:.2f} ms")
        print(
            "  References: "
            f"Top-20={sum(is_reference_chunk(x) for x in candidates)}, "
            f"A Top-5={sum(is_reference_chunk(x) for x in text_results[:5])}, "
            f"B Top-5={sum(is_reference_chunk(x) for x in structured_results[:5])}"
        )

    print("\n" + "=" * 120)
    print("Batch-size summary (text-only)")
    baseline = top5_by_batch[8]
    for batch_size in BATCH_SIZES:
        average_ms = sum(timings[batch_size]) / len(timings[batch_size])
        changed = sum(
            current != reference
            for current, reference in zip(top5_by_batch[batch_size], baseline)
        )
        print(
            f"  batch_size={batch_size}: average={average_ms:.2f} ms, "
            f"Top-5 changed vs batch=8 for {changed}/{len(QUERIES)} queries"
        )
    print(
        "Reference totals across five queries: "
        f"Top-20={reference_totals['top20']}/100, "
        f"A Top-5={reference_totals['text_top5']}/25, "
        f"B Top-5={reference_totals['structured_top5']}/25"
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
