from app.database import SessionLocal
from app.models import ChatHistory



db = SessionLocal()



records = db.query(
    ChatHistory
).all()



print("================")
print("聊天历史")
print("================")


for record in records:

    print("----------------")

    print(
        "用户:",
        record.user_id
    )

    print(
        "问题:",
        record.question
    )

    print(
        "答案:",
        record.answer
    )

    print(
        "时间:",
        record.created_time
    )



db.close()