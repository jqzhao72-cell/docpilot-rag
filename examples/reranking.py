from rag.retrieval import Retriever
from rag.reranker import Reranker



question = "员工一年有多少天年假？"



# 第一阶段:
# Chroma召回

retriever = Retriever()


docs = retriever.search(
    question,
    "employee",
    top_k=5
)



print("================")
print("Chroma结果")
print("================")


for d in docs:

    print(
        d["content"][:50]
    )

    print(
        d["score"]
    )



# 第二阶段:
# Rerank


reranker = Reranker()


new_docs = reranker.rerank(
    question,
    docs,
    top_k=3
)



print("\n================")
print("Reranker结果")
print("================")


for d in new_docs:

    print("----------------")

    print(
        d["content"]
    )


    print(
        "Rerank:",
        d["rerank_score"]
    )
