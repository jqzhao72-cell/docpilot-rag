from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.database import SessionLocal
from app.models import User
from app.permissions import VALID_ROLES, get_user_by_id, normalize_user_role



router = APIRouter()


class RoleUpdateRequest(BaseModel):
    operator_user_id: int
    role: str



# =====================
# 用户注册
# =====================


@router.post("/register")
def register(
    user_data: dict
):


    username = user_data.get(
        "username"
    )


    password = user_data.get(
        "password"
    )



    if not username or not password:

        return {

            "error":
            "用户名和密码不能为空"

        }



    db = SessionLocal()



    # 查询用户是否存在

    exist_user = db.query(
        User
    ).filter(
        User.username == username
    ).first()



    if exist_user:


        db.close()


        return {

            "error":
            "用户名已经存在"

        }



    # Public registration can never grant a privileged role. Any role supplied
    # by the client is deliberately ignored.
    new_user = User(

        username=username,

        password=password,

        role="employee"

    )



    db.add(
        new_user
    )


    db.commit()


    db.refresh(
        new_user
    )


    db.close()



    return {


        "message":
        "注册成功",


        "user_id":
        new_user.id,


        "username":
        new_user.username


    }

#用户登录
@router.post("/login")
def login(
    user_data: dict
):


    username = user_data.get(
        "username"
    )

    password = user_data.get(
        "password"
    )


    db = SessionLocal()


    user = db.query(
        User
    ).filter(
        User.username == username,
        User.password == password
    ).first()



    if not user:

        db.close()

        return {

            "error":
            "用户名或密码错误"

        }



    role = normalize_user_role(user.role)
    result = {

        "message":
        "登录成功",

        "user_id":
        user.id,

        "username":
        user.username,

        "role":
        role

    }

    db.close()
    return result


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, request: RoleUpdateRequest):
    if request.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户角色只允许 employee、hr 或 admin",
        )

    db = SessionLocal()
    try:
        operator = get_user_by_id(db, request.operator_user_id)
        if operator.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以修改用户角色",
            )

        target_user = db.query(User).filter(User.id == user_id).first()
        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="目标用户不存在",
            )

        target_user.role = request.role
        db.commit()
        db.refresh(target_user)
        return {
            "user_id": target_user.id,
            "username": target_user.username,
            "new_role": target_user.role,
        }
    finally:
        db.close()
