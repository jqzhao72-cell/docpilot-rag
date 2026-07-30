def build_prompt(question, retrieved_docs):
    """
    构建带引用信息的RAG Prompt

    retrieved_docs:
    [
        {
            "content": "...",
            "source": "...",
            "chunk_id": 0
        }
    ]
    """


    context_text = ""


    for i, doc in enumerate(retrieved_docs):

        context_text += f"""
资料{i+1}:

内容:
{doc["content"]}

来源:
{doc["source"]}

文本块:
{doc["chunk_id"]}

----------------
"""


    prompt = f"""
你是一个企业知识库助手。

请严格根据提供的资料回答问题。

要求：

1. 不要编造资料中没有的信息。
2. 如果资料无法回答，请说明无法确定。
3. 回答结束后，列出参考来源。


资料:

{context_text}


用户问题:

{question}


请生成答案:
"""


    return prompt