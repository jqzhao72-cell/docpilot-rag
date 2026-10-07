from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

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


from rag.pipeline import PaperRAGPipeline


from datetime import datetime

import json
import os


# =========================
# 创建FastAPI应用
# =========================

app = FastAPI(

    title="Enterprise RAG API",

    description="企业文档智能助手",

    version="1.0.0"

)


cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

paper_rag_pipeline = PaperRAGPipeline()


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
        get_user_by_id(
            db,
            user_id
        )


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

    pipeline_result = paper_rag_pipeline.answer(
        question,
        history_text=history_text,
    )


    # =========================
    # 8. Reranker排序
    # =========================

    retrieval_results = pipeline_result["retrieval_results"]


    # =========================
    # 9. 构建Prompt
    # =========================

    retrieval_by_id = {
        str(result.get("id")): result
        for result in retrieval_results
    }


    # =========================
    # 10. DeepSeek生成答案
    # =========================

    answer = pipeline_result["answer"]


    # =========================
    # 11. 整理引用来源
    # =========================

    sources = []
    for source in pipeline_result["sources"]:
        retrieval_result = retrieval_by_id.get(str(source.get("id")), {})
        sources.append({
            **source,
            "text": retrieval_result.get("text", ""),
        })


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
        sources,

        "retrieval_results":
        retrieval_results,

        "timings":
        pipeline_result["timings"]

    }
