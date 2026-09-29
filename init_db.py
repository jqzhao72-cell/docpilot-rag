from app.database import Base, engine

from app.models import (
    User,
    ChatHistory,
    Conversation,
    Message
)


Base.metadata.create_all(
    bind=engine
)
# 根据这些模型，在 engine 连接的数据库里创建对应表。

print("数据库创建完成")