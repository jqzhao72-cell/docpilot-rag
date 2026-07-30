from rag.retrieval import Retriever


retriever = Retriever()


question = "员工一年有多少天年假？"


results = retriever.search(
    question,
    top_k=3
)


print("================")
print("检索结果")
print("================")


for item in results:

    print("----------------")

    print(
        "内容:"
    )

    print(
        item["content"]
    )


    print(
        "来源:"
    )

    print(
        item["source"]
    )


    print(
        "Chunk:"
    )

    print(
        item["chunk_id"]
    )


    print(
        "距离:"
    )

    print(
        item["score"]
    )