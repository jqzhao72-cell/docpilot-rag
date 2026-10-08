import json
from fastapi import APIRouter, Depends, HTTPException, Response
from app.database import get_db
from app.auth import get_current_user
from app.models import Conversation, Message
from app.schemas import ConversationCreate, ConversationUpdate
from app.schemas import ConversationResponse, MessageResponse

router = APIRouter(tags=["会话"])

def owned_conversation(db, conversation_id, user):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(404, "会话不存在")
    return conversation

def conversation_dict(item):
    return {key: getattr(item, key) for key in
            ("id", "user_id", "title", "knowledge_base", "created_time", "updated_time")}

def parse_sources(value):
    try:
        result = json.loads(value or "[]")
        return result if isinstance(result, list) else []
    except (ValueError, TypeError):
        return []

@router.post("/conversations", status_code=201, response_model=ConversationResponse)
def create_conversation(data: ConversationCreate, user=Depends(get_current_user), db=Depends(get_db)):
    item = Conversation(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    return conversation_dict(item)

@router.get("/conversations", response_model=list[ConversationResponse])
def get_conversations(user=Depends(get_current_user), db=Depends(get_db)):
    return [conversation_dict(x) for x in db.query(Conversation).filter_by(user_id=user.id)
            .order_by(Conversation.updated_time.desc(), Conversation.id.desc()).all()]

@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def get_messages(conversation_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    owned_conversation(db, conversation_id, user)
    return [{"id": x.id, "conversation_id": x.conversation_id, "role": x.role,
             "content": x.content, "sources": parse_sources(x.sources), "created_time": x.created_time}
            for x in db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_time, Message.id)]

@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def rename_conversation(conversation_id: int, data: ConversationUpdate,
                        user=Depends(get_current_user), db=Depends(get_db)):
    item = owned_conversation(db, conversation_id, user)
    item.title = data.title
    db.commit()
    return conversation_dict(item)

@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    from app.knowledge import knowledge_lock
    with knowledge_lock():
        item = owned_conversation(db, conversation_id, user)
        db.query(Message).filter_by(conversation_id=item.id).delete()
        db.delete(item)
        db.commit()
    return Response(status_code=204)
