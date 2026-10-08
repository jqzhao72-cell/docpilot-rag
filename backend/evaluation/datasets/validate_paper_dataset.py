"""Validate candidate annotations without retrieval, model loading or LLM calls."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

BACKEND = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(dataset: dict, corpus: dict) -> dict:
    chunks = corpus["chunks"]
    by_id = {f"paper-{c['global_chunk_index']}": c for c in chunks}
    require(len(by_id) == len(chunks) == dataset["corpus"]["chunk_count"], "Corpus count/ID mismatch")
    actual_sources = Counter(c["source"] for c in chunks)
    require(actual_sources == Counter({s["source"]: s["chunk_count"] for s in dataset["corpus"]["sources"]}), "Source counts mismatch")
    queries = dataset["queries"]
    require(len(queries) == 30, "Expected 30 candidate queries")
    require(len({q["id"] for q in queries}) == len(queries), "Duplicate query IDs")
    require(len({q["query"] for q in queries}) == len(queries), "Duplicate queries")
    for q in queries:
        label = q["id"]
        for field in ("id", "query", "source", "question_type", "review_notes"):
            require(isinstance(q[field], str) and bool(q[field].strip()), f"{label}: empty {field}")
        require(q["review_status"] in ("pending", "approved", "rejected"), f"{label}: invalid review status")
        require(isinstance(q["expected_answer_points"], list) and bool(q["expected_answer_points"]), f"{label}: missing answer points")
        require(all(isinstance(p, str) and p.strip() for p in q["expected_answer_points"]), f"{label}: invalid answer point")
        ids = q["relevant_chunk_ids"]
        require(isinstance(ids, list) and bool(ids) and len(ids) == len(set(ids)), f"{label}: invalid chunk IDs")
        pages = set()
        for chunk_id in ids:
            require(chunk_id in by_id, f"{label}: unknown chunk {chunk_id}")
            c = by_id[chunk_id]
            require(c["source"] == q["source"], f"{label}: source mismatch for {chunk_id}")
            require(isinstance(c["text"], str) and bool(c["text"].strip()), f"{label}: empty chunk")
            require(type(c["page_start"]) is int and type(c["page_end"]) is int and 1 <= c["page_start"] <= c["page_end"], f"{label}: invalid corpus pages")
            pages.update(range(c["page_start"], c["page_end"] + 1))
        require(all(type(p) is int for p in q["relevant_pages"]), f"{label}: noninteger page")
        require(q["relevant_pages"] == sorted(pages), f"{label}: page mismatch")
    return {
        "validation": "passed",
        "formal_metrics_executed": False,
        "dataset_status": dataset["status"],
        "query_count": len(queries),
        "corpus_chunk_count": len(chunks),
        "referenced_unique_chunk_count": len({i for q in queries for i in q["relevant_chunk_ids"]}),
        "by_source": dict(Counter(q["source"] for q in queries)),
        "by_question_type": dict(Counter(q["question_type"] for q in queries)),
        "by_review_status": dict(Counter(q["review_status"] for q in queries)),
    }


def verify_chroma(path: Path, collection: str, chunks: list[dict]) -> int:
    # Direct SQLite read-only access: no Chroma startup/migrations or embeddings.
    require(path.is_file(), f"Missing Chroma database: {path}")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT e.embedding_id, m.key, m.string_value, m.int_value "
            "FROM embeddings e JOIN segments s ON e.segment_id=s.id "
            "JOIN collections c ON s.collection=c.id "
            "JOIN embedding_metadata m ON e.id=m.id WHERE c.name=?",
            (collection,),
        ).fetchall()
    finally:
        db.close()
    stored = {}
    for chunk_id, key, text, number in rows:
        stored.setdefault(chunk_id, {})[key] = text if text is not None else number
    expected_ids = {f"paper-{c['global_chunk_index']}" for c in chunks}
    require(set(stored) == expected_ids, "Chroma ID set differs from pinned corpus")
    for c in chunks:
        chunk_id = f"paper-{c['global_chunk_index']}"
        metadata = stored[chunk_id]
        for field in ("source", "page_start", "page_end"):
            require(metadata.get(field) == c[field], f"Chroma {chunk_id}: {field} mismatch")
        require(metadata.get("chroma:document") == c["text"], f"Chroma {chunk_id}: text mismatch")
    return len(stored)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("paper_retrieval_eval.json"))
    parser.add_argument("--corpus", type=Path, default=BACKEND / "data/evaluation/clean_paper_chunks.json")
    parser.add_argument("--chroma-db", type=Path, help="Optional read-only check against the local Chroma SQLite schema")
    args = parser.parse_args()
    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        raw = args.corpus.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == dataset["corpus"]["sha256"], "Corpus SHA256 mismatch; obtain the pinned snapshot, do not silently relabel")
        result = validate(dataset, json.loads(raw))
        result["corpus_sha256"] = dataset["corpus"]["sha256"]
        result["chroma_verified_count"] = verify_chroma(args.chroma_db, dataset["corpus"]["collection_name"], json.loads(raw)["chunks"]) if args.chroma_db else None
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, f"Validation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
