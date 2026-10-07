from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi import Form

from pathlib import Path
import shutil


from rag.ingestion.loader import load_document
from rag.ingestion.splitter import split_text

from rag.embedding import EmbeddingModel
from rag.vector_store import ChromaVectorStore
from app.database import SessionLocal
from app.permissions import (
    can_upload_document,
    get_user_by_id,
    validate_document_role,
)



# 创建路由

router = APIRouter()



# 上传文件保存目录

UPLOAD_DIR = Path(
    "data/documents"
)


UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)



# 初始化组件

embedding_model = EmbeddingModel()

vector_store = ChromaVectorStore()



@router.post("/upload")
async def upload_file(

    file: UploadFile = File(...),

    role: str = Form("employee"),

    user_id: int = Form(...),

):
    # Complete authorization before touching the filesystem, parsing the file,
    # embedding content, or writing anything to Chroma.
    validate_document_role(role)
    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if not can_upload_document(user.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前用户无权上传该权限级别的文档",
            )
    finally:
        db.close()

    safe_filename = Path(file.filename or "").name
    if not safe_filename or safe_filename != file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不合法",
        )

    # ======================
    # 1. 保存上传文件
    # ======================

    file_path = (
        UPLOAD_DIR
        /
        safe_filename
    )


    with open(
        file_path,
        "wb"
    ) as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )



    print(
        "文件保存:",
        file_path
    )



    # ======================
    # 2. 文档解析
    # ======================

    text = load_document(
        str(file_path)
    )


    print(
        "文本长度:",
        len(text)
    )



    # ======================
    # 3. 文档切分
    # ======================

    chunk_records = split_text(
        text
    )

    chunks = [
        chunk["text"]
        for chunk in chunk_records
    ]


    print(
        "Chunk数量:",
        len(chunks)
    )



    # ======================
    # 4. Embedding
    # ======================

    embeddings = embedding_model.encode(
        chunks
    )



    # ======================
    # 5. 创建metadata
    # ======================

    metadatas = []


    for i, chunk_record in enumerate(chunk_records):

       metadatas.append(

{
    "source":
    safe_filename,

    "chunk_id":
    i,

    "role":
    role,

    **chunk_record["metadata"],
}

)

    # ======================
    # 6. 保存到Chroma
    # ======================

    vector_store.add_documents(
        chunks,
        embeddings,
        metadatas
    )



    return {

        "filename":
        safe_filename,


        "chunks":
        len(chunks),


        "message":
        "文档上传成功，知识库已更新"

    }
