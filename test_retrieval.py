from rag.retrieval import Retriever


retriever = Retriever()


question = "员工一年有多少天年假？"


results = retriever.search(
    question,
    top_k=3
)


print("================")
print("完整结果")
print("================")

print(results)