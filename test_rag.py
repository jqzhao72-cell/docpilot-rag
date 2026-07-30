from rag.retrieval import Retriever
from rag.prompt import build_prompt
from rag.llm import DeepSeekLLM



question = "员工一年有多少天年假？"



# 检索

retriever = Retriever()


docs = retriever.search(
    question,
    top_k=3
)



# Prompt

prompt = build_prompt(
    question,
    docs
)



print(prompt)



# LLM

llm = DeepSeekLLM()


answer = llm.generate(
    prompt
)


print("================")
print("答案")
print("================")

print(answer)