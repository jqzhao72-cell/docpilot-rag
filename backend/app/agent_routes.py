"""HTTP transport only; orchestration lives in business and Agent services."""
from fastapi import APIRouter, Depends
from app.auth import get_current_user, bearer
from app.database import get_db
from app.schemas import ChatRequest, AgentChatResponse
from app.chat_service import run_turn

router = APIRouter(tags=['Agent'])


@router.post('/agent/chat', response_model=AgentChatResponse)
def agent_chat(request: ChatRequest, user=Depends(get_current_user),
               credentials=Depends(bearer), db=Depends(get_db)):
    return run_turn(request, credentials, db, mode='agent')
