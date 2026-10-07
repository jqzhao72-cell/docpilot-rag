"""Run the complete paper RAG pipeline against the five standard queries."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.pipeline import PaperRAGPipeline


QUERIES = (
    "triple-negative breast cancer treatment",
    "AKR1C3",
    "STAT1 IRF7",
    "chemotherapy resistance",
    "tumor immune microenvironment",
)


def main() -> int:
    pipeline = PaperRAGPipeline()
    totals: list[dict[str, float]] = []

    for query in QUERIES:
        result = pipeline.answer(query)
        timings = result["timings"]
        totals.append(timings)

        print("\n" + "=" * 110)
        print(f"Query: {query}")
        print(f"Answer:\n{result['answer']}")
        print("Sources:")
        for source in result["sources"]:
            print(
                f"  [{source['index']}] id={source['id']} "
                f"source={source['source']} page={source['page']} "
                f"section={source['section']!r} type={source['chunk_type']}"
            )
        print(
            "Timings: "
            f"retrieval={timings['retrieval_ms']:.2f} ms, "
            f"reranker={timings['reranker_ms']:.2f} ms, "
            f"DeepSeek={timings['deepseek_api_ms']:.2f} ms, "
            f"total={timings['total_ms']:.2f} ms"
        )

    print("\n" + "=" * 110)
    count = len(totals)
    print(
        "Average timings: "
        f"retrieval={sum(item['retrieval_ms'] for item in totals) / count:.2f} ms, "
        f"reranker={sum(item['reranker_ms'] for item in totals) / count:.2f} ms, "
        f"DeepSeek={sum(item['deepseek_api_ms'] for item in totals) / count:.2f} ms, "
        f"total={sum(item['total_ms'] for item in totals) / count:.2f} ms"
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
