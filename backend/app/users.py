from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import User, AuthSession
from app.auth import bearer, get_current_user, require_admin, hash_password, verify_password, issue_session, token_digest
from app.permissions import normalize_user_role, VALID_ROLES
from app.schemas import Credentials, Registration, RoleUpdateRequest
from app.schemas import UserResponse, RegistrationResponse, LoginResponse, UserListResponse

router = APIRouter(tags=["认证与用户"])

def public_user(user):
    return {"user_id": user.id, "username": user.username, "role": normalize_user_role(user.role)}

@router.post("/register", status_code=201, response_model=RegistrationResponse)
def register(data: Registration, db=Depends(get_db)):
    username = data.username.strip()
    if not username:
        raise HTTPException(422, "用户名不能为空")
    user = User(username=username, password=hash_password(data.password), role="employee")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名已经存在")
    return {"message": "注册成功", **public_user(user)}

@router.post("/login", response_model=LoginResponse)
def login(data: Credentials, db=Depends(get_db)):
    user = db.query(User).filter(User.username == data.username.strip()).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(401, "用户名或密码错误")
    if normalize_user_role(user.role) not in VALID_ROLES:
        raise HTTPException(403, "用户角色无效")
    return {**public_user(user), **issue_session(db, user)}

@router.get("/users/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    return public_user(user)

@router.post("/logout", status_code=204)
def logout(user=Depends(get_current_user), credentials=Depends(bearer), db=Depends(get_db)):
    db.query(AuthSession).filter(AuthSession.token_hash == token_digest(credentials.credentials)).delete()
    db.commit()
    return Response(status_code=204)

@router.get("/users", response_model=UserListResponse)
def list_users(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
               user=Depends(require_admin), db=Depends(get_db)):
    query = db.query(User)
    return {"items": [public_user(x) for x in query.order_by(User.id).offset(offset).limit(limit)],
            "total": query.count()}

@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, request: RoleUpdateRequest, operator=Depends(require_admin), db=Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "目标用户不存在")
    if target.id == operator.id and request.role != "admin":
        raise HTTPException(409, "不能撤销自己的管理员权限")
    target.role = request.role
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()
    db.commit()
    return public_user(target)
