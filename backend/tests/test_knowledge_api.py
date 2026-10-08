"""Exercise live-corpus adaptation and upload rollback without external services."""
import io
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException, UploadFile
from app import documents, knowledge


class Vector(list):
    def tolist(self):
        return list(self)


class Encoder:
    def encode(self, texts):
        return [Vector([1., 0.]) for _ in texts]


class Collection:
    metadata = {"hnsw:space": "cosine"}

    def __init__(self):
        self.rows = {}
        self.fail_add = False
        self.queried_ids = []

    def get(self, ids=None, where=None, include=None):
        selected = [(key, row) for key, row in self.rows.items()
                    if (ids is None or key in ids)
                    and (where is None or all(row["metadata"].get(k) == v for k, v in where.items()))]
        return {"ids": [k for k, _ in selected], "metadatas": [r["metadata"] for _, r in selected],
                "documents": [r["text"] for _, r in selected]}

    def add(self, ids, documents, embeddings, metadatas):
        for key, text, meta in zip(ids, documents, metadatas):
            self.rows[key] = {"text": text, "metadata": meta}
        if self.fail_add:
            raise RuntimeError("simulated index failure")

    def delete(self, ids):
        for key in ids:
            self.rows.pop(key, None)

    def update(self, ids, metadatas):
        for key, metadata in zip(ids, metadatas):
            self.rows[key]["metadata"] = metadata

    def query(self, query_embeddings, ids, n_results, include):
        self.queried_ids = ids
        return {"ids": [ids[:n_results]], "distances": [[0.1] * min(n_results, len(ids))]}


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.collection = Collection()
        self.patches = [patch("app.knowledge.collection_for", return_value=self.collection),
                        patch("app.documents.collection_for", return_value=self.collection),
                        patch("app.documents.knowledge_lock", lambda: nullcontext()),
                        patch("app.documents.safe_file", lambda name: Path(self.directory.name) / name),
                        patch("app.documents.embedding_for", return_value=Encoder()),
                        patch("app.knowledge.embedding_for", return_value=Encoder())]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.directory.cleanup()

    def upload(self, name="sample.txt", role="employee"):
        with patch("rag.ingestion.loader.load_document", return_value="leave policy evidence"), \
             patch("rag.ingestion.splitter.split_text", return_value=[{"text": "leave policy evidence", "metadata": {}}]):
            return documents.upload_document(UploadFile(filename=name, file=io.BytesIO(b"leave policy evidence")),
                                             role, "company", SimpleNamespace(role="hr"))

    def test_upload_is_visible_to_both_retrievers_then_deleted(self):
        from rag.hybrid_retrieval import HybridRetriever
        from rag.sparse_retrieval import BM25Retriever
        result = self.upload()
        self.assertEqual(result["chunks"], 1)
        chunks = knowledge.visible_chunks("company", "employee")
        dense = knowledge.DenseAdapter("company", chunks)
        sparse = BM25Retriever(chunks=chunks)
        result = HybridRetriever(dense_retriever=dense, bm25_retriever=sparse).search("leave policy")
        self.assertEqual(result[0]["id"], chunks[0]["id"])
        self.assertIn("dense_rank", result[0])
        self.assertIn("bm25_rank", result[0])
        with self.assertRaises(HTTPException) as error:
            self.upload()
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len(self.collection.rows), 1)
        documents.delete_document("sample.txt", "company", SimpleNamespace(role="hr"))
        self.assertEqual(knowledge.visible_chunks("company", "employee"), [])
        self.assertFalse((Path(self.directory.name) / "sample.txt").exists())
        self.assertEqual(len(list((Path(self.directory.name) / ".trash").iterdir())), 1)

    def test_failed_index_write_rolls_back_file_and_partial_vectors(self):
        self.collection.fail_add = True
        with self.assertRaises(RuntimeError):
            self.upload()
        self.assertEqual(self.collection.rows, {})
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_role_filter_runs_before_dense_and_sparse_retrieval(self):
        from rag.sparse_retrieval import BM25Retriever
        for i, role in enumerate(("employee", "hr", "admin", None)):
            self.collection.rows[str(i)] = {"text": "leave policy", "metadata": {"source": str(i), "role": role}}
        for role, count in (("employee", 1), ("hr", 2), ("admin", 4)):
            chunks = knowledge.visible_chunks("paper", role)
            dense = knowledge.DenseAdapter("paper", chunks).search("leave")
            sparse = BM25Retriever(chunks=chunks).search("leave")
            self.assertEqual(len(dense), count)
            self.assertEqual(len(sparse), count)
            self.assertEqual(set(self.collection.queried_ids), {x["id"] for x in chunks})

    def test_mixed_roles_use_highest_role_and_require_all_chunks(self):
        self.collection.rows = {
            "a": {"text": "x", "metadata": {"source": "mixed", "role": "admin"}},
            "b": {"text": "y", "metadata": {"source": "mixed", "role": "hr"}},
        }
        self.assertEqual(documents.list_documents("company", SimpleNamespace(role="admin"))[0]["role"], "admin")
        self.assertEqual(documents.list_documents("company", SimpleNamespace(role="hr")), [])
        self.assertEqual(knowledge.visible_chunks("company", "hr"), [])

    def test_invalid_file_paths_rejected(self):
        for filename in ("../x.txt", "a/b.txt", "a\\b.txt", "a:b", ""):
            with self.subTest(filename=filename), self.assertRaises(HTTPException):
                knowledge.safe_file(filename)

    def test_pipeline_prompt_and_sources_only_contain_authorized_evidence(self):
        self.upload()
        self.collection.rows["private"] = {"text": "TOP_SECRET leave policy",
                                             "metadata": {"source": "private", "role": "admin"}}
        class Reranker:
            def rerank(self, query, docs, top_k):
                return docs[:top_k]
        class LLM:
            prompt = None
            def generate(self, prompt):
                self.prompt = prompt
                return "supported [1]"
        llm = LLM()
        with patch("app.knowledge.generation_components", return_value=(Reranker(), llm)):
            result = knowledge.answer_question("leave policy", "company", "employee", "")
        self.assertNotIn("TOP_SECRET", llm.prompt)
        self.assertIn("leave policy evidence", llm.prompt)
        self.assertEqual(result["sources"][0]["source"], "sample.txt")
        self.assertEqual(result["sources"][0]["text"], "leave policy evidence")
        self.assertEqual(result["answer"], "supported [1]")


if __name__ == "__main__":
    unittest.main()
