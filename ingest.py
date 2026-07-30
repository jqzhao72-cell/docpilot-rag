from rag.vector_store import ChromaVectorStore
from pathlib import Path

from rag.ingestion.loader import load_document
from rag.ingestion.splitter import split_text

from sentence_transformers import SentenceTransformer
store = ChromaVectorStore()


# =====================
# 1. 配置路径
# =====================

DOCUMENT_DIR = "data/documents"


# =====================
# 2. 加载Embedding模型
# =====================

model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)



# =====================
# 3. 初始化Chroma
# =====================



# =====================
# 4. 遍历文档
# =====================

all_chunks = []

metadatas = []


for file in Path(DOCUMENT_DIR).iterdir():

    print(
        "正在处理:",
        file.name
    )


    text = load_document(
        str(file)
    )


    chunks = split_text(
        text
    )


    for index, chunk in enumerate(chunks):

        all_chunks.append(chunk)


        metadatas.append(
            {
                "source": file.name,
                "chunk_id": index
            }
        )



print(
    "总Chunk数量:",
    len(all_chunks)
)



# =====================
# 5. Embedding
# =====================


embeddings = model.encode(
    all_chunks
)



# =====================
# 6. 写入Chroma
# =====================


store.add_documents(
    chunks=all_chunks,
    embeddings=embeddings,
    metadatas=metadatas
)


print("知识库构建完成")