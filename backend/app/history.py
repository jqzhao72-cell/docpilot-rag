"""History is a read model of messages, never a second write destination."""
from fastapi import APIRouter, Depends, Query
from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Conversation, Message
from app.conversations import parse_sources
from app.schemas import HistoryResponse

router = APIRouter(tags=["历史"])

def history_records(db, user_id=None):
    query = db.query(Message, Conversation).join(Conversation, Conversation.id == Message.conversation_id)
    if user_id is not None:
        query = query.filter(Conversation.user_id == user_id)
    result, pending = [], {}
    for message, conversation in query.order_by(Message.created_time, Message.id):
        if message.role == "user":
            pending[conversation.id] = message.content
        elif message.role == "assistant" and conversation.id in pending:
            result.append({"id": message.id, "conversation_id": conversation.id,
                           "user_id": conversation.user_id, "question": pending.pop(conversation.id),
                           "answer": message.content, "sources": parse_sources(message.sources),
                           "created_time": message.created_time})
    return list(reversed(result))

@router.get("/history", response_model=list[HistoryResponse])
def get_history(user=Depends(get_current_user), db=Depends(get_db)):
    return history_records(db, user.id)

@router.get("/admin/history", response_model=list[HistoryResponse])
def get_all_history(user_id: int | None = Query(None), user=Depends(require_admin), db=Depends(get_db)):
    return history_records(db, user_id)
