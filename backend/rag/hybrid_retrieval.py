"""Reciprocal-rank fusion of dense and BM25 paper retrieval."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rag.retrieval import Retriever
from rag.sparse_retrieval import BM25Retriever


def reciprocal_rank_fusion(
    dense_results: Sequence[Mapping[str, Any]],
    bm25_results: Sequence[Mapping[str, Any]],
    k: int = 60,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Fuse two rankings by chunk id using ``sum(1 / (k + rank))``."""
    if k < 0:
        raise ValueError("RRF k must be non-negative")
    if top_k is not None and (isinstance(top_k, bool) or top_k <= 0):
        raise ValueError("top_k must be a positive integer or None")

    fused: dict[str, dict[str, Any]] = {}
    for name, ranking in (("dense", dense_results), ("bm25", bm25_results)):
        seen: set[str] = set()
        for rank, result in enumerate(ranking, start=1):
            chunk_id = str(result["id"])
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            entry = fused.setdefault(chunk_id, dict(result))
            entry.setdefault("rrf_score", 0.0)
            entry["rrf_score"] += 1.0 / (k + rank)
            entry[f"{name}_rank"] = rank
            entry[f"{name}_score"] = result.get("score")
            # Fill metadata absent from whichever ranking first introduced it.
            for key, value in result.items():
                if entry.get(key) is None:
                    entry[key] = value

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            -item["rrf_score"],
            item.get("dense_rank", float("inf")),
            item.get("bm25_rank", float("inf")),
            str(item["id"]),
        ),
    )
    for item in ranked:
        item["score"] = item["rrf_score"]
    return ranked[:top_k] if top_k is not None else ranked


class HybridRetriever:
    """Retrieve Dense Top-N and BM25 Top-N, then fuse them with RRF."""

    def __init__(
        self,
        dense_retriever: Retriever | None = None,
        bm25_retriever: BM25Retriever | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.dense = dense_retriever or Retriever()
        self.bm25 = bm25_retriever or BM25Retriever()
        self.rrf_k = rrf_k

    def search_with_components(
        self,
        query: str,
        top_k: int = 20,
        dense_top_n: int = 20,
        bm25_top_n: int = 20,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        dense_results = self.dense.search(
            query, top_k=dense_top_n, metadata_filter=metadata_filter
        )
        bm25_results = self.bm25.search(
            query, top_k=bm25_top_n, metadata_filter=metadata_filter
        )
        hybrid_results = reciprocal_rank_fusion(
            dense_results, bm25_results, k=self.rrf_k, top_k=top_k
        )
        return {"dense": dense_results, "bm25": bm25_results, "hybrid": hybrid_results}

    def search(
        self,
        query: str,
        top_k: int = 20,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.search_with_components(
            query,
            top_k=top_k,
            dense_top_n=20,
            bm25_top_n=20,
            metadata_filter=metadata_filter,
        )["hybrid"]
