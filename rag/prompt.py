def build_prompt(question, contexts):
    """
    构造RAG Prompt

    question:
        用户问题

    contexts:
        检索到的文本列表
    """


    context_text = "\n".join(
        contexts
    )


    prompt = f"""
你是一个企业知识库助手。

请严格根据提供的资料回答问题。

如果资料中没有答案，
请回答：
"根据现有资料无法确定。"


资料:
----------------
{context_text}
----------------


问题:
{question}


答案:
"""


    return prompt