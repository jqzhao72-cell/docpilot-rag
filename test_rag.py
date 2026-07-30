from rag.retrieval import Retriever
from rag.prompt import build_prompt
from rag.llm import DeepSeekLLM



# 用户问题

question = "员工一年有多少天年假？"



# 1. 检索

retriever = Retriever()


results = retriever.search(
    question,
    top_k=3
)


contexts = results["documents"][0]



# 2. 构建Prompt

prompt = build_prompt(
    question,
    contexts
)



print("================")
print("Prompt")
print("================")

print(prompt)



# 3. 调用DeepSeek

llm = DeepSeekLLM()


answer = llm.generate(
    prompt
)



print("\n================")
print("Answer")
print("================")

print(answer)