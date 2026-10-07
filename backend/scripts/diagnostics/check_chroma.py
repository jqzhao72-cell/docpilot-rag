import chromadb

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_collection(
    name="company_docs"
)

data = collection.get()

files = {}

for metadata in data["metadatas"]:

    source = metadata.get(
        "source",
        "未知文件"
    )

    role = metadata.get(
        "role",
        "无role"
    )

    if source not in files:

        files[source] = {
            "count": 0,
            "roles": set()
        }

    files[source]["count"] += 1

    files[source]["roles"].add(
        role
    )


print("===== 当前Chroma文档汇总 =====")

for source, info in files.items():

    print(
        f"\n文件: {source}"
    )

    print(
        f"Chunk数量: {info['count']}"
    )

    print(
        f"Role: {info['roles']}"
    )