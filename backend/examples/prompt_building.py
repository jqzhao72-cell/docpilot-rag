from rag.prompt import build_prompt



question = "员工一年有多少天年假？"



contexts = [
    {"content": "正式员工每年享有10天带薪年假。", "source": "年假制度", "chunk_id": 0},
    {"content": "员工申请年假时，需要提前三个工作日提交申请。", "source": "年假制度", "chunk_id": 1}
]



prompt = build_prompt(
    question,
    contexts
)


print(prompt)
