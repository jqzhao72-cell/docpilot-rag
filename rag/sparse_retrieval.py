"""In-memory BM25 retrieval for the cleaned paper chunks."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_CHUNKS_PATH = Path("data/evaluation/clean_paper_chunks.json")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Tokenize prose while preserving biomedical identifiers and compounds."""
    normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", text).lower()
    tokens = TOKEN_PATTERN.findall(normalized)
    # Index both the full compound and its components, e.g. triple-negative.
    return tokens + [part for token in tokens if "-" in token for part in token.split("-")]


def _matches_filter(chunk: Mapping[str, Any], metadata_filter: Mapping[str, Any] | None) -> bool:
    if not metadata_filter:
        return True
    for key, expected in metadata_filter.items():
        actual = chunk.get(key)
        if isinstance(expected, Mapping):
            if "$eq" in expected and actual != expected["$eq"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class BM25Retriever:
    """A dependency-free BM25Okapi index over clean paper chunks."""

    def __init__(
        self,
        chunks_path: str | Path = DEFAULT_CHUNKS_PATH,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        payload = json.loads(Path(chunks_path).read_text(encoding="utf-8"))
        self.chunks: Sequence[dict[str, Any]] = payload["chunks"]
        if not self.chunks:
            raise ValueError("paper chunk corpus is empty")
        self.k1 = k1
        self.b = b
        self.term_frequencies: list[Counter[str]] = []
        self.document_lengths: list[int] = []
        document_frequencies: dict[str, int] = defaultdict(int)

        for chunk in self.chunks:
            frequencies = Counter(tokenize(chunk.get("text", "")))
            self.term_frequencies.append(frequencies)
            self.document_lengths.append(sum(frequencies.values()))
            for term in frequencies:
                document_frequencies[term] += 1

        self.document_count = len(self.chunks)
        self.average_document_length = sum(self.document_lengths) / self.document_count
        self.idf = {
            term: math.log(1.0 + (self.document_count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequencies.items()
        }

    def _score(self, query_terms: Counter[str], index: int) -> float:
        frequencies = self.term_frequencies[index]
        length_ratio = self.document_lengths[index] / self.average_document_length
        score = 0.0
        for term, query_frequency in query_terms.items():
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            denominator = frequency + self.k1 * (1.0 - self.b + self.b * length_ratio)
            score += query_frequency * self.idf.get(term, 0.0) * frequency * (self.k1 + 1.0) / denominator
        return score

    def search(
        self,
        query: str,
        top_k: int = 20,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return positive-scoring BM25 results in descending score order."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")

        query_terms = Counter(tokenize(query))
        scored = [
            (self._score(query_terms, index), index)
            for index, chunk in enumerate(self.chunks)
            if _matches_filter(chunk, metadata_filter)
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))

        results = []
        for score, index in scored:
            if score <= 0 or len(results) >= top_k:
                break
            chunk = self.chunks[index]
            global_index = chunk.get("global_chunk_index", index)
            results.append({
                "id": f"paper-{global_index}",
                "text": chunk.get("text", ""),
                "source": chunk.get("source"),
                "chunk_type": chunk.get("chunk_type"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "section": chunk.get("section"),
                "subsection": chunk.get("subsection"),
                "chunk_index": chunk.get("chunk_index"),
                "score": float(score),
            })
        return results
