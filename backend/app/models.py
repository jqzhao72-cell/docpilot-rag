from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import DateTime

from datetime import datetime

from app.database import Base

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime
)

from datetime import datetime

from app.database import Base

# =====================
# 用户表
# =====================

class User(Base):


    __tablename__ = "users"



    id = Column(

        Integer,

        primary_key=True,

        index=True

    )


    username = Column(

        String(50),

        unique=True,

        nullable=False

    )


    password = Column(

        String(100),

        nullable=False

    )


    role = Column(

        String(50),

        default="employee"

    )


    created_time = Column(

        DateTime,

        default=datetime.now

    )



# =====================
# 聊天历史表
# =====================

class ChatHistory(Base):


    __tablename__ = "chat_history"



    id = Column(

        Integer,

        primary_key=True,

        index=True

    )


    user_id = Column(

        Integer

    )


    session_id = Column(

        String(100)

    )


    question = Column(

        Text,

        nullable=False

    )


    answer = Column(

        Text,

        nullable=False

    )


    sources = Column(

        Text

    )


    created_time = Column(

        DateTime,

        default=datetime.now

    )
    # =========================
# 会话表
# =========================

class Conversation(Base):

    __tablename__ = "conversations"

    # 每个会话自己的唯一ID
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 这个会话属于哪个用户
    user_id = Column(
        Integer,
        nullable=False
    )

    # 会话标题
    # 例如：
    # "员工年假咨询"
    # "财务报销问题"
    title = Column(
        String(200),
        default="新会话"
    )

    # 会话创建时间
    created_time = Column(
        DateTime,
        default=datetime.now
    )

    # 会话最后更新时间
    # 用户继续聊天时，后面会更新这个字段
    updated_time = Column(
        DateTime,
        default=datetime.now
    )


# =========================
# 消息表
# =========================

class Message(Base):

    __tablename__ = "messages"

    # 每一条消息自己的唯一ID
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 这条消息属于哪个会话
    conversation_id = Column(
        Integer,
        nullable=False
    )

    # 消息角色
    # user      = 用户说的话
    # assistant = AI说的话
    role = Column(
        String(20),
        nullable=False
    )

    # 消息正文
    content = Column(
        Text,
        nullable=False
    )

    # RAG引用来源
    # 用户消息一般为空
    # AI消息可以保存引用文档
    sources = Column(
        Text,
        nullable=True
    )

    # 消息创建时间
    created_time = Column(
        DateTime,
        default=datetime.now
    )
