"""Central role policy. HTTP identity is resolved by app.auth, never client IDs."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.models import User


VALID_ROLES = ("employee", "hr", "admin")


def normalize_user_role(user_role: str) -> str:
    # Compatibility with the project's former default role. It is deliberately
    # mapped to the least-privileged role and is never written back implicitly.
    return "employee" if user_role == "user" else user_role


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或未登录",
        )
    normalized_role = normalize_user_role(user.role)
    if normalized_role != user.role:
        # Change only the in-memory view; do not silently migrate existing data.
        set_committed_value(user, "role", normalized_role)
    if user.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户角色无效，请联系管理员",
        )
    return user


def get_allowed_document_roles(user_role: str) -> list[str]:
    if user_role == "employee":
        return ["employee"]
    if user_role == "hr":
        return ["employee", "hr"]
    if user_role == "admin":
        return list(VALID_ROLES)
    return []


def get_retrieval_where(user_role: str) -> dict | None:
    """Build the Chroma filter for a role; admins intentionally have none."""
    if user_role == "employee":
        return {"role": "employee"}
    if user_role == "hr":
        return {"role": {"$in": ["employee", "hr"]}}
    if user_role == "admin":
        return None
    # Unknown database roles fail closed. Normal API paths reject these earlier.
    return {"role": "__no_access__"}


def validate_document_role(document_role: str) -> None:
    if document_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文档角色只允许 employee、hr 或 admin",
        )


def can_upload_document(user_role: str, document_role: str) -> bool:
    return user_role in ("hr", "admin") and document_role in get_allowed_document_roles(
        user_role
    )


def can_delete_document(user_role: str, document_role: str) -> bool:
    return user_role in ("hr", "admin") and document_role in get_allowed_document_roles(
        user_role
    )
