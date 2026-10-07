from app.database import SessionLocal
from app.models import User


db = SessionLocal()

users = db.query(User).all()

for user in users:
    print(
        "user_id =", user.id,
        "| username =", user.username,
        "| role =", user.role
    )

db.close()