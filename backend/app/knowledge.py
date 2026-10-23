"""Knowledge-base adapters; scoring, fusion, reranking and generation stay in rag/."""
from contextlib import contextmanager
import logging
from functools import lru_cache
from pathlib import Path
from threading import RLock
from time import monotonic
from fastapi import HTTPException
from filelock import FileLock, Timeout
from app.database import BACKEND_ROOT
from app.permissions import get_allowed_document_roles, VALID_ROLES

BASES = {"company": ("company_docs", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
         "paper": ("paper_docs_bge_m3", "BAAI/bge-m3")}
_thread_lock = RLock()

@contextmanager
def knowledge_lock(timeout=10.0):
    deadline = monotonic() + timeout
    if not _thread_lock.acquire(timeout=timeout):
        raise HTTPException(409, "知识库正在处理其他请求，请稍后重试")
    try:
        try:
            with FileLock(str(BACKEND_ROOT / ".knowledge.lock"), timeout=max(0, deadline - monotonic())):
                yield
        except Timeout:
            raise HTTPException(409, "知识库正在处理其他请求，请稍后重试")
    finally:
        _thread_lock.release()

@lru_cache
def chroma_client():
    import chromadb
    return chromadb.PersistentClient(path=str(BACKEND_ROOT / "chroma_db"))

def collection_for(knowledge_base):
    if knowledge_base not in BASES:
        raise HTTPException(422, "未知知识库")
    return chroma_client().get_or_create_collection(
        name=BASES[knowledge_base][0], metadata={"hnsw:space": "cosine"})

@lru_cache
def embedding_for(knowledge_base):
    from rag.embedding import EmbeddingModel
    return EmbeddingModel(BASES[knowledge_base][1], normalize_embeddings=True)

def document_role(metadata):
    # Unclassified legacy content is not public by default.
    return metadata.get("role") or "admin"

def read_chunks(knowledge_base):
    raw = collection_for(knowledge_base).get(include=["metadatas", "documents"])
    return [{**(meta or {}), "role": document_role(meta or {}), "id": item_id, "text": text or ""}
            for item_id, meta, text in zip(raw["ids"], raw["metadatas"], raw["documents"])]

def visible_chunks(knowledge_base, user_role):
    allowed = get_allowed_document_roles(user_role)
    chunks = read_chunks(knowledge_base)
    blocked = {x.get("source") for x in chunks if x["role"] not in allowed}
    return [x for x in chunks if x["role"] in allowed and x.get("source") not in blocked]

def document_chunks(knowledge_base, filename, user_role):
    chunks = [x for x in read_chunks(knowledge_base) if x.get("source") == filename]
    if not chunks or any(x["role"] not in get_allowed_document_roles(user_role) for x in chunks):
        raise HTTPException(404, "文档不存在或无权访问")
    return chunks

def safe_file(filename):
    if not filename or Path(filename).name != filename or any(c in filename for c in ('/', '\\', ':')):
        raise HTTPException(400, "文件名不合法")
    root = (BACKEND_ROOT / "data" / "documents").resolve()
    path = (root / filename).resolve()
    if path.parent != root:
        raise HTTPException(400, "文件名不合法")
    return path

class DenseAdapter:
    def __init__(self, knowledge_base, chunks):
        self.knowledge_base = knowledge_base
        self.chunks = {x["id"]: x for x in chunks}

    def search(self, query, top_k=20, metadata_filter=None):
        if not self.chunks:
            return []
        collection = collection_for(self.knowledge_base)
        if (collection.metadata or {}).get("hnsw:space") != "cosine":
            raise HTTPException(503, "知识库索引不是 cosine，请重新建立索引")
        vector = embedding_for(self.knowledge_base).encode([query])[0].tolist()
        raw = collection.query(query_embeddings=[vector], ids=list(self.chunks),
                               n_results=min(top_k, len(self.chunks)), include=["distances"])
        return [{**self.chunks[item_id], "distance": float(distance), "score": 1.0-float(distance)}
                for item_id, distance in zip(raw["ids"][0], raw["distances"][0])]

@lru_cache
def reranker_component():
    from rag.reranker import Reranker
    return Reranker()

@lru_cache
def generation_components():
    from rag.llm import DeepSeekLLM
    return reranker_component(), DeepSeekLLM()

def evidence_retriever(knowledge_base, chunks, reranker=None):
    from rag.evidence import EvidenceRetriever
    from rag.hybrid_retrieval import HybridRetriever
    from rag.sparse_retrieval import BM25Retriever
    hybrid = HybridRetriever(dense_retriever=DenseAdapter(knowledge_base, chunks),
                             bm25_retriever=BM25Retriever(chunks=chunks))
    return EvidenceRetriever(hybrid_retriever=hybrid, reranker=reranker or reranker_component())

def search_evidence(query, top_k, knowledge_base, chunks):
    """Called with a server-authorized corpus snapshot, never a model-supplied role."""
    if not chunks:
        return {'query': query, 'has_evidence': False, 'evidence': []}
    from rag.pipeline import build_sources
    # Keep the production final top-5 intact, then limit presentation only.
    results = evidence_retriever(knowledge_base, chunks).retrieve_evidence(query)['retrieval_results'][:top_k]
    sources = build_sources(results)
    by_id = {x['id']: x for x in chunks}
    evidence = [{**source, 'chunk_id': source['id'], 'text': by_id[source['id']]['text'],
                 'knowledge_base': knowledge_base} for source in sources if source['id'] in by_id]
    return {'query': query, 'has_evidence': bool(evidence), 'evidence': evidence}

def answer_question(question, knowledge_base, user_role, history_text):
    started = monotonic()
    from rag.pipeline import PaperRAGPipeline
    chunks = visible_chunks(knowledge_base, user_role)
    if not chunks:
        return {"answer": "当前知识库没有您有权访问的内容，请上传文档或联系管理员设置文档权限。",
                "sources": [], "retrieval_results": [], "timings": {"total_ms": (monotonic() - started) * 1000}}
    reranker, llm = generation_components()
    retriever = evidence_retriever(knowledge_base, chunks, reranker)
    pipeline = PaperRAGPipeline(hybrid_retriever=retriever.hybrid_retriever, reranker=reranker, llm=llm)
    preparation_ms = (monotonic() - started) * 1000
    result = pipeline.answer(question, metadata_filter={"role": {"$in": get_allowed_document_roles(user_role)}},
                             history_text=history_text)
    by_id = {x["id"]: x for x in chunks}
    result["sources"] = [{**x, "text": by_id.get(x["id"], {}).get("text", ""),
                           "knowledge_base": knowledge_base} for x in result["sources"]]
    # Include corpus preparation and cold model loads previously omitted from total_ms.
    # Do not log queries, evidence text, credentials or generated answers.
    result["timings"]["total_ms"] = (monotonic() - started) * 1000
    logging.getLogger(__name__).info("RAG preparation_ms=%.1f timings=%s", preparation_ms, result["timings"])
    return result
