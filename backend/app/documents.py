import os
import tempfile
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile, Response
from fastapi.responses import FileResponse
from app.auth import get_current_user, require_admin
from app.schemas import KnowledgeBase, Role, RoleUpdateRequest
from app.schemas import DocumentResponse, UploadResponse, DocumentContentResponse, DocumentRoleResponse
from app.permissions import can_upload_document, can_delete_document
from app.knowledge import (collection_for, read_chunks, document_chunks, safe_file,
                           knowledge_lock, embedding_for)

router = APIRouter(tags=["文档"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(knowledge_base: KnowledgeBase = "company", user=Depends(get_current_user)):
    from app.permissions import get_allowed_document_roles, VALID_ROLES
    grouped = {}
    with knowledge_lock():
        for chunk in read_chunks(knowledge_base):
            if chunk.get("source"):
                grouped.setdefault(chunk["source"], []).append(chunk)
    result = []
    for filename, chunks in grouped.items():
        roles = {x["role"] for x in chunks}
        if not roles.issubset(set(get_allowed_document_roles(user.role))):
            continue
        role = max(roles, key=lambda x: VALID_ROLES.index(x))
        result.append({"filename": filename, "chunks": len(chunks), "role": role,
                       "knowledge_base": knowledge_base})
    return sorted(result, key=lambda x: x["filename"].casefold())

@router.get("/documents/{filename}/content", response_model=DocumentContentResponse)
def view_document(filename: str, knowledge_base: KnowledgeBase = "company", user=Depends(get_current_user)):
    with knowledge_lock():
        chunks = document_chunks(knowledge_base, filename, user.role)
        return {"filename": filename, "knowledge_base": knowledge_base,
                "chunks": [{"text": x["text"], "section": x.get("section"),
                            "page_start": x.get("page_start"), "page_end": x.get("page_end")} for x in chunks]}

@router.get("/documents/{filename}/download")
def download_document(filename: str, knowledge_base: KnowledgeBase = "company", user=Depends(get_current_user)):
    with knowledge_lock():
        document_chunks(knowledge_base, filename, user.role)
        if knowledge_base != "company":
            raise HTTPException(404, "此知识库仅提供已索引正文")
        path = safe_file(filename)
        if not path.is_file():
            raise HTTPException(404, "原文件不存在，可查看已索引正文")
        return Response(path.read_bytes(), media_type="application/octet-stream",
                        headers={"Content-Disposition": FileResponse(path, filename=filename).headers["content-disposition"]})

@router.put("/documents/{filename}/role", response_model=DocumentRoleResponse)
def update_document_role(filename: str, data: RoleUpdateRequest, knowledge_base: KnowledgeBase = "company",
                         user=Depends(require_admin)):
    with knowledge_lock():
        chunks = document_chunks(knowledge_base, filename, user.role)
        collection = collection_for(knowledge_base)
        raw = collection.get(ids=[x["id"] for x in chunks], include=["metadatas"])
        collection.update(ids=raw["ids"], metadatas=[{**(x or {}), "role": data.role} for x in raw["metadatas"]])
    return {"filename": filename, "role": data.role}

@router.post("/documents", status_code=201, response_model=UploadResponse)
def upload_document(file: UploadFile = File(...), role: Role = Form("employee"),
                    knowledge_base: KnowledgeBase = Form("company"), user=Depends(get_current_user)):
    if not can_upload_document(user.role, role):
        raise HTTPException(403, "无权上传该权限级别的文档")
    if knowledge_base != "company":
        raise HTTPException(422, "在线上传使用企业知识库；论文库通过现有论文导入流程维护")
    path = safe_file(file.filename or "")
    if path.suffix.lower() not in (".pdf", ".docx", ".txt"):
        raise HTTPException(415, "仅支持 PDF、DOCX、TXT")
    from rag.ingestion.loader import load_document
    from rag.ingestion.splitter import split_text
    with knowledge_lock():
        collection = collection_for(knowledge_base)
        if path.exists() or collection.get(where={"source": path.name}, include=[])["ids"]:
            raise HTTPException(409, "已存在同名文档，请更换文件名或先删除旧文档")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
        ids = []
        published = False
        try:
            size = 0
            with os.fdopen(fd, "wb") as buffer:
                while data := file.file.read(1024 * 1024):
                    size += len(data)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "文件不能超过 25 MB")
                    buffer.write(data)
            try:
                records = split_text(load_document(temporary))
            except Exception as error:
                raise HTTPException(422, "文件解析失败，请检查文件格式和内容") from error
            if not records:
                raise HTTPException(422, "未提取到可索引的文本")
            texts = [x["text"] for x in records]
            vectors = embedding_for(knowledge_base).encode(texts)
            ids = [str(uuid.uuid4()) for _ in texts]
            metadata = [{**x["metadata"], "source": path.name, "role": role, "chunk_id": i}
                        for i, x in enumerate(records)]
            os.replace(temporary, path)
            published = True
            collection.add(ids=ids, documents=texts, embeddings=[x.tolist() for x in vectors], metadatas=metadata)
            return {"filename": path.name, "chunks": len(texts), "role": role,
                    "knowledge_base": knowledge_base, "message": "文档已入库，可直接用于企业知识库问答"}
        except Exception:
            try:
                if ids:
                    collection.delete(ids=ids)
            finally:
                if published:
                    path.unlink(missing_ok=True)
            raise
        finally:
            Path(temporary).unlink(missing_ok=True)

@router.delete("/documents/{filename}", status_code=204)
def delete_document(filename: str, knowledge_base: KnowledgeBase = "company", user=Depends(get_current_user)):
    with knowledge_lock():
        chunks = document_chunks(knowledge_base, filename, user.role)
        if not all(can_delete_document(user.role, x["role"]) for x in chunks):
            raise HTTPException(403, "无权删除该文档")
        path = safe_file(filename) if knowledge_base == "company" else None
        moved = None
        if path and path.exists():
            trash = path.parent / ".trash"
            trash.mkdir(exist_ok=True)
            moved = trash / (uuid.uuid4().hex + "-" + path.name)
            path.replace(moved)
        try:
            collection_for(knowledge_base).delete(ids=[x["id"] for x in chunks])
        except Exception:
            if moved:
                moved.replace(path)
            raise
    return Response(status_code=204)
