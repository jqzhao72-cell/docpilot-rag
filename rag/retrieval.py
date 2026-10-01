"""Dense retrieval backed by BGE-M3 and a cosine Chroma collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import chromadb

from rag.embedding import EmbeddingModel


DEFAULT_COLLECTION_NAME = "paper_docs_bge_m3"
DEFAULT_TOP_K = 5


class Retriever:
    """Run dense cosine retrieval over Chroma with BGE-M3 query vectors."""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        persist_directory: str | Path = "./chroma_db",
    ) -> None:
        self.model = EmbeddingModel("BAAI/bge-m3", normalize_embeddings=True)
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection_name = collection_name
        self.collection = self._get_cosine_collection(collection_name)

    def _get_cosine_collection(self, collection_name: str):
        """Load a collection and reject non-cosine indexes explicitly."""
        collection = self.client.get_collection(name=collection_name)
        space = (collection.metadata or {}).get("hnsw:space")
        if space != "cosine":
            raise ValueError(
                f"Collection {collection_name!r} must use cosine distance; "
                f"found hnsw:space={space!r}."
            )
        return collection

    def search(
        self,
        question: str,
        user_role: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        collection_name: str | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return Top-K matches; ``score`` is ``1 - cosine distance``.

        ``user_role`` remains accepted for source compatibility. Paper
        retrieval filtering is controlled by the explicit metadata filter.
        """
        del user_role
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")

        target_name = collection_name or self.collection_name
        collection = self.collection if target_name == self.collection_name else self._get_cosine_collection(target_name)
        query_embedding = self.model.encode([question.strip()])[0].tolist()
        query_args: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if metadata_filter:
            query_args["where"] = dict(metadata_filter)

        raw = collection.query(**query_args)
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[dict[str, Any]] = []
        for item_id, text, metadata, raw_distance in zip(ids, documents, metadatas, distances):
            metadata = metadata or {}
            distance = float(raw_distance)
            results.append({
                "id": item_id,
                "text": text or "",
                "score": 1.0 - distance,
                "distance": distance,
                "source": metadata.get("source"),
                "chunk_type": metadata.get("chunk_type"),
                "section": metadata.get("section"),
                "subsection": metadata.get("subsection"),
                "page_start": metadata.get("page_start"),
                "page_end": metadata.get("page_end"),
                "chunk_index": metadata.get("chunk_index"),
            })
        return results
