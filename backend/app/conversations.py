from fastapi import APIRouter

from app.database import SessionLocal
from app.models import Conversation, Message


# 创建路由对象
router = APIRouter()


# =========================
# 1. 创建新会话
# =========================

@router.post("/conversations")
def create_conversation(data: dict):

    # 从前端请求体中获取 user_id
    user_id = data.get("user_id")

    # 如果前端没有传 title
    # 就默认叫“新会话”
    title = data.get(
        "title",
        "新会话"
    )


    # 判断用户是否登录
    if not user_id:

        return {
            "error": "用户未登录"
        }


    # 打开数据库会话
    db = SessionLocal()


    # 创建一个 Conversation 对象
    conversation = Conversation(

        user_id=user_id,

        title=title

    )


    # 加入数据库
    db.add(
        conversation
    )


    # 提交事务
    db.commit()


    # 刷新对象
    # 这样可以拿到数据库自动生成的 id
    db.refresh(
        conversation
    )


    # 关闭数据库
    db.close()


    # 返回创建结果
    return {

        "id":
        conversation.id,

        "user_id":
        conversation.user_id,

        "title":
        conversation.title

    }


# =========================
# 2. 获取某个用户的会话列表
# =========================

@router.get("/conversations/user/{user_id}")
def get_user_conversations(
    user_id: int
):

    # 打开数据库
    db = SessionLocal()


    # 查询 Conversation 表
    # 只取属于这个用户的会话
    conversations = (

        db.query(
            Conversation
        )

        .filter(
            Conversation.user_id == user_id
        )

        # 最近更新的会话排在前面
        .order_by(
            Conversation.updated_time.desc()
        )

        .all()
    )


    # 用来保存返回结果
    result = []


    # 遍历查询结果
    for conversation in conversations:

        result.append({

            "id":
            conversation.id,

            "user_id":
            conversation.user_id,

            "title":
            conversation.title,

            "created_time":
            str(
                conversation.created_time
            ),

            "updated_time":
            str(
                conversation.updated_time
            )

        })


    # 关闭数据库
    db.close()


    # 返回会话列表
    return result


# =========================
# 3. 获取某个会话中的全部消息
# =========================

@router.get(
    "/conversations/{conversation_id}/messages"
)
def get_conversation_messages(
    conversation_id: int
):

    # 打开数据库
    db = SessionLocal()


    # 查询 Message 表
    # 只取这个 conversation_id 的消息
    messages = (

        db.query(
            Message
        )

        .filter(
            Message.conversation_id
            ==
            conversation_id
        )

        # 聊天记录按照时间从旧到新排列
        .order_by(
            Message.created_time.asc()
        )

        .all()
    )


    # 保存最终返回结果
    result = []


    # 遍历消息
    for message in messages:

        result.append({

            "id":
            message.id,

            "conversation_id":
            message.conversation_id,

            "role":
            message.role,

            "content":
            message.content,

            "sources":
            message.sources,

            "created_time":
            str(
                message.created_time
            )

        })


    # 关闭数据库
    db.close()


    # 返回消息列表
    return result