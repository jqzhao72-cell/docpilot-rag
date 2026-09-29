def build_prompt(
    question,
    retrieved_docs,
    history_text=""
):
    """
    构建带短期会话记忆和引用信息的RAG Prompt

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


    # =========================
    # 1. 拼接RAG检索到的企业资料
    # =========================

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


    # =========================
    # 2. 构建最终Prompt
    # =========================

    prompt = f"""
你是一个企业知识库助手。

请结合历史对话理解用户当前问题，
并严格根据提供的企业资料回答。

要求：

1. 历史对话只用于理解用户当前问题的上下文。
2. 企业事实必须以提供的企业资料为依据。
3. 不要编造资料中没有的信息。
4. 如果资料无法回答，请说明无法根据当前资料确定。
5. 回答结束后，列出参考来源。


历史对话:

{history_text}


企业资料:

{context_text}


当前用户问题:

{question}


请生成答案:
"""


    return prompt