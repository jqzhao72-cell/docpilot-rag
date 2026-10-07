"""Smoke-test BGE-M3 dense retrieval against the paper collection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retrieval import DEFAULT_COLLECTION_NAME, Retriever

QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--chunk-type", choices=("text", "figure", "table"))
    return parser.parse_args()


def compact(text: str, limit: int = 180) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= limit else one_line[: limit - 1] + "…"


def main() -> int:
    args = parse_args()
    metadata_filter = {"chunk_type": args.chunk_type} if args.chunk_type else None
    retriever = Retriever(collection_name=args.collection_name)
    timings = []
    for query in QUERIES:
        started = perf_counter()
        results = retriever.search(query, top_k=args.top_k, metadata_filter=metadata_filter)
        elapsed_ms = (perf_counter() - started) * 1000
        timings.append(elapsed_ms)
        print(f"\nQuery: {query}\nLatency: {elapsed_ms:.2f} ms")
        for rank, item in enumerate(results, start=1):
            print(
                f"  Top-{rank} score={item['score']:.4f} distance={item['distance']:.4f} "
                f"type={item['chunk_type']} source={item['source']} "
                f"pages={item['page_start']}-{item['page_end']} chunk={item['chunk_index']} id={item['id']}"
            )
            print(f"        {compact(item['text'])}")
    print(f"\nAverage query latency: {sum(timings) / len(timings):.2f} ms")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
