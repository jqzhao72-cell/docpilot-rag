from rag.prompt import build_prompt



question = "员工一年有多少天年假？"



contexts = [
    "正式员工每年享有10天带薪年假。",
    "员工申请年假时，需要提前三个工作日提交申请。"
]



prompt = build_prompt(
    question,
    contexts
)


print(prompt)