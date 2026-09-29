from rag.retrieval import Retriever
from rag.reranker import Reranker
from rag.prompt import build_prompt
from rag.llm import DeepSeekLLM



question = "员工一年有多少天年假？"



# =====================
# 1. Chroma召回
# =====================

retriever = Retriever()


docs = retriever.search(
    question,
    top_k=5
)



print("================")
print("Chroma召回")
print("================")


for d in docs:

    print(
        d["content"][:50]
    )



# =====================
# 2. Reranker精排
# =====================

reranker = Reranker()


docs = reranker.rerank(
    question,
    docs,
    top_k=3
)



print("================")
print("Reranker排序")
print("================")


for d in docs:

    print(
        d["content"][:50]
    )



# =====================
# 3. 构造Prompt
# =====================

prompt = build_prompt(
    question,
    docs
)



print(prompt)



# =====================
# 4. DeepSeek生成
# =====================

llm = DeepSeekLLM()


answer = llm.generate(
    prompt
)


print("================")
print("答案")
print("================")


print(answer)