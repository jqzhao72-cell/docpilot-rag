"""FastAPI composition; expensive RAG components load only when requested."""
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import BACKEND_ROOT, engine, get_db
from app.auth import get_current_user, bearer
from app.models import Message
from app.schemas import ChatRequest, ChatResponse
from app.conversations import router as conversations_router, owned_conversation
from app.users import router as users_router
from app.history import router as history_router
from app.documents import router as documents_router

load_dotenv(BACKEND_ROOT / ".env")

@asynccontextmanager
async def lifespan(app):
    from app.migrations import upgrade
    upgrade(engine)
    yield

app = FastAPI(title="DocPilot API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
for router in (users_router, conversations_router, history_router, documents_router):
    app.include_router(router)

@app.get("/")
def root():
    return {"message": "DocPilot API running", "version": "2.0.0"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user=Depends(get_current_user), credentials=Depends(bearer), db=Depends(get_db)):
    from app.knowledge import answer_question, knowledge_lock
    # Serialize index mutation/deletion and turn persistence across worker processes.
    with knowledge_lock():
        db.expire_all()
        user = get_current_user(credentials, db)
        initial_role = user.role
        conversation = owned_conversation(db, request.conversation_id, user)
        previous = db.query(Message).filter_by(conversation_id=conversation.id).order_by(Message.created_time.desc(), Message.id.desc()).limit(6).all()
        history_text = "\n".join(f"{m.role}: {m.content}" for m in reversed(previous))
        try:
            result = answer_question(request.question, conversation.knowledge_base, user.role, history_text)
        except HTTPException:
            raise
        except Exception:
            logging.exception("RAG request failed")
            raise HTTPException(503, "问答服务暂时不可用，请稍后重试")
        # Re-read role/session after an expensive generation; a revoked session must not commit.
        db.rollback()
        refreshed = get_current_user(credentials, db)
        if refreshed.role != initial_role:
            raise HTTPException(409, "权限已变化，请重新提问")
        conversation = owned_conversation(db, request.conversation_id, user)
        sources = result["sources"]
        db.add_all([Message(conversation_id=conversation.id, role="user", content=request.question),
                    Message(conversation_id=conversation.id, role="assistant", content=result["answer"],
                            sources=json.dumps(sources, ensure_ascii=False))])
        conversation.updated_time = datetime.utcnow()
        db.commit()
        return {"conversation_id": conversation.id, "question": request.question, **result}
