import chromadb


# 连接你的Chroma数据库

client = chromadb.PersistentClient(
    path="./chroma_db"
)


# 获取集合

collection = client.get_collection(
    name="company_docs"
)



# 获取metadata

result = collection.get(
    include=[
        "metadatas"
    ]
)



print("================")
print("知识库统计")
print("================")


print(
    "Chunk数量:",
    len(result["metadatas"])
)



print("\nMetadata示例:")


for meta in result["metadatas"][:10]:

    print(meta)