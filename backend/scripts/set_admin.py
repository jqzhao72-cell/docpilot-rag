from app.database import SessionLocal
from app.models import User


db = SessionLocal()


user = db.query(User).filter(
    User.id == 1
).first()


if not user:
    print("没有找到 user_id=1")
else:

    user.role = "admin"

    db.commit()

    db.refresh(user)

    print(
        "修改成功：",
        "user_id =", user.id,
        "| username =", user.username,
        "| role =", user.role
    )


db.close()