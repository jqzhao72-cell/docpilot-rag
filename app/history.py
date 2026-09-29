from fastapi import APIRouter

from app.database import SessionLocal
from app.models import ChatHistory



router = APIRouter()



# =====================
# 查询全部历史
# =====================

@router.get("/history")
def get_history():


    db = SessionLocal()


    records = db.query(
        ChatHistory
    ).order_by(
        ChatHistory.created_time.desc()
    ).all()



    result = []


    for record in records:

        result.append({

            "id":
            record.id,

            "user_id":
            record.user_id,

            "question":
            record.question,

            "answer":
            record.answer,

            "sources":
            record.sources,

            "created_time":
            str(record.created_time)

        })


    db.close()


    return result




# =====================
# 查询指定用户历史
# =====================

@router.get("/history/user/{user_id}")
def get_user_history(
    user_id:int
):


    db = SessionLocal()


    records = db.query(
        ChatHistory
    ).filter(
        ChatHistory.user_id == user_id
    ).order_by(
        ChatHistory.created_time.desc()
    ).all()



    result=[]


    for record in records:


        result.append({

            "id":
            record.id,

            "user_id":
            record.user_id,

            "question":
            record.question,

            "answer":
            record.answer,

            "sources":
            record.sources,

            "created_time":
            str(record.created_time)

        })


    db.close()


    return result