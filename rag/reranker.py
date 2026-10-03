"""Batch reranking for Hybrid Retrieval candidates."""

from __future__ import annotations

from pathlib import Path
import re
from time import perf_counter
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from sentence_transformers import CrossEncoder


DEFAULT_MODEL_PATH = Path("models/models/BAAI--bge-reranker-base/snapshots/master")
RerankerInputMode = Literal["text", "structured"]
REFERENCE_LABEL = re.compile(r"\b(?:references|bibliography)\b", re.IGNORECASE)
NUMBERED_CITATION = re.compile(r"^\s*(?:\[\d{1,3}\]|\d{1,3}\.)\s*")
AUTHOR_CITATION = re.compile(r"\bet\s+al\.", re.IGNORECASE)
IDENTIFIER_CITATION = re.compile(
    r"(?:\bdoi\s*:|https?://doi\.org/|\bPMID\s*:)", re.IGNORECASE
)
JOURNAL_CITATION = re.compile(
    r"(?:\b(?:19|20)\d{2}\s*;\s*\d+(?:\s*\(\d+\))?\s*:\s*\d+|"
    r"\b\d+\s*,\s*\d+[–-]\d+\s*\((?:19|20)\d{2}\))"
)


def reference_signals(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    """Return lightweight citation signals found in candidate metadata/text."""
    section = str(candidate.get("section") or "")
    subsection = str(candidate.get("subsection") or "")
    text = str(candidate.get("text", candidate.get("content", "")) or "")
    combined = f"{section}\n{subsection}\n{text}"
    signals = []
    if REFERENCE_LABEL.search(f"{section} {subsection}"):
        signals.append("reference_label")
    if NUMBERED_CITATION.match(section) or NUMBERED_CITATION.match(text):
        signals.append("numbered_citation")
    if AUTHOR_CITATION.search(combined):
        signals.append("et_al")
    if IDENTIFIER_CITATION.search(combined):
        signals.append("doi_or_pmid")
    if JOURNAL_CITATION.search(combined):
        signals.append("journal_volume_pages")
    return tuple(signals)


def is_reference_candidate(candidate: Mapping[str, Any]) -> bool:
    """Mark likely bibliography chunks without deleting or downweighting them."""
    signals = set(reference_signals(candidate))
    if "reference_label" in signals:
        return True
    citation_evidence = signals & {"et_al", "doi_or_pmid", "journal_volume_pages"}
    return (
        "numbered_citation" in signals and bool(citation_evidence)
    ) or len(citation_evidence) >= 2


def build_reranker_text(
    candidate: Mapping[str, Any],
    input_mode: RerankerInputMode = "text",
) -> str:
    """Build the document side of a cross-encoder pair."""
    text = candidate.get("text", candidate.get("content", ""))
    if not isinstance(text, str):
        text = str(text)
    if input_mode == "text":
        return text
    if input_mode != "structured":
        raise ValueError("input_mode must be 'text' or 'structured'")

    section = candidate.get("section") or ""
    subsection = candidate.get("subsection") or ""
    chunk_type = candidate.get("chunk_type") or "unknown"
    return (
        f"Section: {section}\n"
        f"Subsection: {subsection}\n"
        f"Chunk type: {chunk_type}\n"
        f"Text: {text}"
    )


class Reranker:
    """Rerank Hybrid candidates with the local BGE cross-encoder."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        batch_size: int = 4,
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
        input_mode: RerankerInputMode = "text",
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
        if input_mode not in {"text", "structured"}:
            raise ValueError("input_mode must be 'text' or 'structured'")

        prepared: list[dict[str, Any]] = []
        pairs: list[tuple[str, str]] = []
        for rrf_rank, candidate in enumerate(candidates, start=1):
            item = dict(candidate)
            text = build_reranker_text(item, "text")
            rerank_input = build_reranker_text(item, input_mode)
            item["text"] = text
            item.setdefault("dense_score", None)
            item.setdefault("bm25_score", None)
            item.setdefault("rrf_score", item.get("score"))
            item["rrf_rank"] = rrf_rank
            item["rerank_input_mode"] = input_mode
            item["rerank_input"] = rerank_input
            item["is_reference"] = is_reference_candidate(item)
            item["reference_signals"] = reference_signals(item)
            prepared.append(item)
            pairs.append((query.strip(), rerank_input))

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


def second_stage_rank_fusion(
    hybrid_results: Sequence[Mapping[str, Any]],
    reranked_results: Sequence[Mapping[str, Any]],
    k: int = 60,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Fuse the original Hybrid rank and pure reranker rank with RRF."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    fused: dict[str, dict[str, Any]] = {}
    for hybrid_rank, result in enumerate(hybrid_results, start=1):
        item = dict(result)
        item["rrf_rank"] = hybrid_rank
        item["is_reference"] = is_reference_candidate(item)
        item["reference_signals"] = reference_signals(item)
        item["second_stage_rrf_score"] = 1.0 / (k + hybrid_rank)
        fused[str(item["id"])] = item

    seen: set[str] = set()
    for rerank_rank, result in enumerate(reranked_results, start=1):
        candidate_id = str(result["id"])
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        if candidate_id not in fused:
            continue
        item = fused[candidate_id]
        item.update({
            key: value
            for key, value in result.items()
            if key not in {"final_rank", "rank_change"}
        })
        item["rerank_rank"] = rerank_rank
        item["second_stage_rrf_score"] += 1.0 / (k + rerank_rank)

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            -item["second_stage_rrf_score"],
            item["rrf_rank"],
            item.get("rerank_rank", float("inf")),
            str(item["id"]),
        ),
    )
    final_results = ranked[:top_k]
    for final_rank, item in enumerate(final_results, start=1):
        item["final_rank"] = final_rank
        item["rank_change"] = item["rrf_rank"] - final_rank
    return final_results
