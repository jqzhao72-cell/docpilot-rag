"""Batch reranking for Hybrid Retrieval candidates."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
from sentence_transformers import CrossEncoder


DEFAULT_MODEL_PATH = Path("models/models/BAAI--bge-reranker-base/snapshots/master")


class Reranker:
    """Rerank Hybrid candidates with the local BGE cross-encoder."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        batch_size: int = 8,
    ) -> None:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        resolved_path = Path(model_path).resolve()
        if not resolved_path.is_dir():
            raise FileNotFoundError(f"Reranker model directory not found: {resolved_path}")

        started = perf_counter()
        self.model = CrossEncoder(str(resolved_path))
        self.model_load_time_ms = (perf_counter() - started) * 1000
        self.model_path = resolved_path
        self.model_name = "BAAI/bge-reranker-base"
        self.batch_size = batch_size

    def rerank(
        self,
        query: str,
        candidates: Sequence[Mapping[str, Any]],
        top_k: int = 5,
        batch_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """Batch-score pairs and return Top-K; positive rank change means promotion."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        effective_batch_size = self.batch_size if batch_size is None else batch_size
        if (
            isinstance(effective_batch_size, bool)
            or not isinstance(effective_batch_size, int)
            or effective_batch_size <= 0
        ):
            raise ValueError("batch_size must be a positive integer")
        if not candidates:
            return []

        prepared: list[dict[str, Any]] = []
        pairs: list[tuple[str, str]] = []
        for rrf_rank, candidate in enumerate(candidates, start=1):
            item = dict(candidate)
            text = item.get("text", item.get("content", ""))
            if not isinstance(text, str):
                text = str(text)
            item["text"] = text
            item.setdefault("dense_score", None)
            item.setdefault("bm25_score", None)
            item.setdefault("rrf_score", item.get("score"))
            item["rrf_rank"] = rrf_rank
            prepared.append(item)
            pairs.append((query.strip(), text))

        raw_scores = self.model.predict(
            pairs,
            batch_size=effective_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        scores = np.asarray(raw_scores).reshape(-1)
        if len(scores) != len(prepared):
            raise RuntimeError("Reranker returned an unexpected number of scores")

        for item, score in zip(prepared, scores):
            item["rerank_score"] = float(score)

        prepared.sort(key=lambda item: (-item["rerank_score"], item["rrf_rank"]))
        final_results = prepared[:top_k]
        for final_rank, item in enumerate(final_results, start=1):
            item["final_rank"] = final_rank
            item["rank_change"] = item["rrf_rank"] - final_rank
        return final_results
