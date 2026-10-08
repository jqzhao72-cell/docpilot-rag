"""Opaque, revocable Bearer sessions; only a token digest is stored."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db
from app.models import AuthSession
from app.permissions import get_user_by_id

bearer = HTTPBearer(auto_error=False)

def hash_password(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt$"+salt+"$"+value

def verify_password(password, stored):
    if not stored.startswith("scrypt$"):
        return False
    try:
        _, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def issue_session(db, user):
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id,
                       expires_at=datetime.utcnow() + timedelta(hours=8)))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": 28800}

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
    session = db.get(AuthSession, token_digest(credentials.credentials))
    if not session or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, "登录已失效，请重新登录", headers={"WWW-Authenticate": "Bearer"})
    return get_user_by_id(db, session.user_id)

def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "只有管理员可以执行此操作")
    return user
