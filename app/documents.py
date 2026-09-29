from fastapi import APIRouter
import chromadb
from fastapi import HTTPException
from pathlib import Path

from app.database import SessionLocal
from app.permissions import can_delete_document, get_allowed_document_roles, get_user_by_id


router = APIRouter()



client = chromadb.PersistentClient(
    path="./chroma_db"
)


collection = client.get_collection(
    name="company_docs"
)



@router.get("/documents")
def list_documents(user_id: int):

    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        allowed_roles = set(get_allowed_document_roles(user.role))
    finally:
        db.close()


    result = collection.get(
        include=[
            "metadatas"
        ]
    )


    documents = {}


    for meta in result["metadatas"]:

        # Compatibility with historical Chroma records: metadata without a
        # role is treated as employee until those records are migrated.
        document_role = meta.get("role", "employee")
        if document_role not in allowed_roles:
            continue

        filename = meta.get("source")
        if not filename:
            continue


        if filename not in documents:

            documents[filename] = {

                "filename":
                filename,

                "chunks":
                0,

                "role":
                document_role
            }

        # A filename can have old/mixed metadata. Report the highest visible
        # role while retaining the existing one-row-per-filename structure.
        if document_role == "hr" or documents[filename]["role"] == "employee":
            documents[filename]["role"] = document_role
        if document_role == "admin":
            documents[filename]["role"] = document_role


        documents[filename]["chunks"] += 1

    return list(
        documents.values()
    )

@router.delete("/documents/{filename}")
def delete_document(
    filename: str,
    user_id: int,
):

    safe_filename = Path(filename).name
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="文件名不合法")

    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        user_role = user.role
    finally:
        db.close()

    target = collection.get(
        where={"source": filename},
        include=["metadatas"],
    )
    metadatas = target.get("metadatas") or []
    if not metadatas:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Missing roles are historical employee documents. If a filename contains
    # mixed-role chunks, require permission for every chunk before deleting any.
    document_roles = {meta.get("role", "employee") for meta in metadatas}
    if not all(can_delete_document(user_role, role) for role in document_roles):
        raise HTTPException(status_code=403, detail="当前用户无权删除该文档")


    # =====================
    # 1. 删除Chroma数据
    # =====================


    collection.delete(
        where={
            "source": filename
        }
    )



    # =====================
    # 2. 删除本地文件
    # =====================


    file_path = Path(
        "data/documents"
    ) / safe_filename


    if file_path.exists():

        file_path.unlink()




    return {

        "message":
        f"{filename} 删除成功"

    }


 
