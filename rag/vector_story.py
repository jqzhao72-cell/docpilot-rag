import chromadb


client = chromadb.PersistentClient(
    path="./chroma_db"
)


collection = client.get_or_create_collection(
    name="company_documents"
)


def save_documents(
    chunks,
    embeddings
):

    ids = [
        str(i)
        for i in range(len(chunks))
    ]


    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist()
    )


    print("向量保存完成")

