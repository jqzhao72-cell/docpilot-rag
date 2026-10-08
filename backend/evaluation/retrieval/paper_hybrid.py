"""Compare Dense, BM25, and RRF Hybrid retrieval on five paper queries."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.hybrid_retrieval import HybridRetriever


QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)


def compact(text: str, limit: int = 130) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_ranking(label: str, results: list[dict], limit: int = 5) -> None:
    print(f"\n{label} Top-{limit}")
    for rank, item in enumerate(results[:limit], start=1):
        ranks = ""
        if label == "Hybrid":
            ranks = f" dense_rank={item.get('dense_rank', '-')} bm25_rank={item.get('bm25_rank', '-')}"
        print(
            f"  {rank}. id={item['id']} score={item['score']:.4f} "
            f"type={item['chunk_type']} source={item['source']} "
            f"page={item['page_start']}-{item['page_end']}{ranks}"
        )
        print(f"     {compact(item['text'])}")


def main() -> int:
    retriever = HybridRetriever()
    print(f"BM25 corpus: {retriever.bm25.document_count} chunks")
    for query in QUERIES:
        print("\n" + "=" * 100)
        print(f"Query: {query}")
        results = retriever.search_with_components(
            query, top_k=20, dense_top_n=20, bm25_top_n=20
        )
        print_ranking("Dense", results["dense"])
        print_ranking("BM25", results["bm25"])
        print_ranking("Hybrid", results["hybrid"])
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
