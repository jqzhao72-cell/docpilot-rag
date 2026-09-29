from fastapi import FastAPI, HTTPException, status

from app.upload import router as upload_router
from app.documents import router as documents_router
from app.history import router as history_router
from app.users import router as users_router
from app.conversations import router as conversations_router

from app.database import SessionLocal

from app.models import (
    ChatHistory,
    Conversation,
    Message
)

from app.permissions import get_user_by_id


from rag.retrieval import Retriever
from rag.reranker import Reranker
from rag.prompt import build_prompt
from rag.llm import DeepSeekLLM


from datetime import datetime

import json


# =========================
# 创建FastAPI应用
# =========================

app = FastAPI(

    title="Enterprise RAG API",

    description="企业文档智能助手",

    version="1.0.0"

)


# =========================
# 注册路由
# =========================

# 文件上传
app.include_router(
    upload_router
)


# 知识库管理
app.include_router(
    documents_router
)


# 旧聊天历史
app.include_router(
    history_router
)


# 用户管理
app.include_router(
    users_router
)


# 新会话管理
app.include_router(
    conversations_router
)


# =========================
# 初始化RAG组件
# =========================

retriever = Retriever()

reranker = Reranker()

llm = DeepSeekLLM()


# =========================
# 首页测试
# =========================

@app.get("/")
def root():

    return {

        "message":
        "Enterprise RAG API running"

    }


# =========================
# 聊天接口
# =========================

@app.post("/chat")
def chat(
    request: dict
):

    # =========================
    # 1. 获取请求参数
    # =========================

    question = request.get(
        "question"
    )

    user_id = request.get(
        "user_id"
    )

    conversation_id = request.get(
        "conversation_id"
    )


    # =========================
    # 2. 基础参数检查
    # =========================

    if not question:

        raise HTTPException(

            status_code=
            status.HTTP_400_BAD_REQUEST,

            detail=
            "question不能为空"

        )


    if user_id is None:

        raise HTTPException(

            status_code=
            status.HTTP_401_UNAUTHORIZED,

            detail=
            "用户未登录"

        )


    if conversation_id is None:

        raise HTTPException(

            status_code=
            status.HTTP_400_BAD_REQUEST,

            detail=
            "conversation_id不能为空"

        )


    # =========================
    # 3. 验证用户和会话
    # =========================

    db = SessionLocal()

    try:

        # 从SQLite获取真实用户
        # 不相信前端自己传role
        user = get_user_by_id(
            db,
            user_id
        )

        user_role = user.role


        # 查询当前conversation
        conversation = (

            db.query(
                Conversation
            )

            .filter(

                Conversation.id
                ==
                conversation_id,

                Conversation.user_id
                ==
                user_id

            )

            .first()

        )


        # 会话不存在
        # 或者这个会话不是当前用户的
        if not conversation:

            raise HTTPException(

                status_code=
                status.HTTP_403_FORBIDDEN,

                detail=
                "会话不存在或无权访问"

            )


        # =========================
        # 4. 读取之前的聊天记录
        # =========================

        history_messages = (

            db.query(
                Message
            )

            .filter(

                Message.conversation_id
                ==
                conversation_id

            )

            .order_by(

                Message.created_time.desc()

            )

            .limit(6)

            .all()

        )


        # 刚才是最新 -> 最旧
        # 现在改成最旧 -> 最新
        history_messages.reverse()


        # =========================
        # 5. 拼接短期会话记忆
        # =========================

        history_text = ""


        for message in history_messages:

            if message.role == "user":

                history_text += (
                    f"用户：{message.content}\n"
                )

            elif message.role == "assistant":

                history_text += (
                    f"助手：{message.content}\n"
                )


        # =========================
        # 6. 保存当前用户消息
        # =========================

        user_message = Message(

            conversation_id=
            conversation_id,

            role=
            "user",

            content=
            question,

            sources=
            None

        )


        db.add(
            user_message
        )


        db.commit()


    finally:

        db.close()


    # =========================
    # 7. Chroma检索
    # =========================

    docs = retriever.search(

        question,

        user_role,

        top_k=5

    )


    # =========================
    # 8. Reranker排序
    # =========================

    docs = reranker.rerank(

        question,

        docs,

        top_k=3

    )


    # =========================
    # 9. 构建Prompt
    # =========================

    prompt = build_prompt(

        question,

        docs,

        history_text

    )


    # =========================
    # 10. DeepSeek生成答案
    # =========================

    answer = llm.generate(

        prompt

    )


    # =========================
    # 11. 整理引用来源
    # =========================

    sources = [

        {

            "file":
            doc["source"],

            "chunk":
            doc["chunk_id"]

        }

        for doc in docs

    ]


    sources_json = json.dumps(

        sources,

        ensure_ascii=False

    )


    # =========================
    # 12. 保存AI回复
    # =========================

    db = SessionLocal()

    try:

        assistant_message = Message(

            conversation_id=
            conversation_id,

            role=
            "assistant",

            content=
            answer,

            sources=
            sources_json

        )


        db.add(
            assistant_message
        )


        # =========================
        # 13. 更新会话最后聊天时间
        # =========================

        conversation = (

            db.query(
                Conversation
            )

            .filter(

                Conversation.id
                ==
                conversation_id

            )

            .first()

        )


        if conversation:

            conversation.updated_time = (
                datetime.now()
            )


        # =========================
        # 14. 暂时继续保存旧ChatHistory
        # =========================
        #
        # 这一部分现在不要删除。
        #
        # 因为你原来的前端/history
        # 可能还依赖ChatHistory。
        #

        history = ChatHistory(

            user_id=
            user_id,

            session_id=
            str(conversation_id),

            question=
            question,

            answer=
            answer,

            sources=
            sources_json

        )


        db.add(
            history
        )


        db.commit()


    finally:

        db.close()


    # =========================
    # 15. 返回结果
    # =========================

    return {

        "conversation_id":
        conversation_id,

        "question":
        question,

        "answer":
        answer,

        "sources":
        sources

    }