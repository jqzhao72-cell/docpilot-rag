import chromadb


client = chromadb.PersistentClient(
    path="./chroma_db"
)


collection = client.get_collection(
    name="company_docs"
)


print(
    "数据数量:",
    collection.count()
)