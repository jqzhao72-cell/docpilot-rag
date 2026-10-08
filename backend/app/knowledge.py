"""Knowledge-base adapters; scoring, fusion, reranking and generation stay in rag/."""
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from threading import RLock
from fastapi import HTTPException
from filelock import FileLock, Timeout
from app.database import BACKEND_ROOT
from app.permissions import get_allowed_document_roles, VALID_ROLES

BASES = {"company": ("company_docs", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
         "paper": ("paper_docs_bge_m3", "BAAI/bge-m3")}
_thread_lock = RLock()

@contextmanager
def knowledge_lock():
    with _thread_lock:
        try:
            with FileLock(str(BACKEND_ROOT / ".knowledge.lock"), timeout=180):
                yield
        except Timeout:
            raise HTTPException(409, "知识库正在处理其他请求，请稍后重试")

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
def generation_components():
    from rag.reranker import Reranker
    from rag.llm import DeepSeekLLM
    return Reranker(), DeepSeekLLM()

def answer_question(question, knowledge_base, user_role, history_text):
    from rag.pipeline import PaperRAGPipeline
    from rag.hybrid_retrieval import HybridRetriever
    from rag.sparse_retrieval import BM25Retriever
    chunks = visible_chunks(knowledge_base, user_role)
    if not chunks:
        return {"answer": "当前知识库没有您有权访问的内容，请上传文档或联系管理员设置文档权限。",
                "sources": [], "retrieval_results": [], "timings": {"total_ms": 0}}
    sparse = BM25Retriever(chunks=chunks)
    hybrid = HybridRetriever(dense_retriever=DenseAdapter(knowledge_base, chunks), bm25_retriever=sparse)
    reranker, llm = generation_components()
    pipeline = PaperRAGPipeline(hybrid_retriever=hybrid, reranker=reranker, llm=llm)
    result = pipeline.answer(question, metadata_filter={"role": {"$in": get_allowed_document_roles(user_role)}},
                             history_text=history_text)
    by_id = {x["id"]: x for x in chunks}
    result["sources"] = [{**x, "text": by_id.get(x["id"], {}).get("text", ""),
                           "knowledge_base": knowledge_base} for x in result["sources"]]
    return result
