"""FastAPI composition; expensive RAG components load only when requested."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import BACKEND_ROOT, engine, get_db
from app.auth import get_current_user, bearer
from app.schemas import ChatRequest, ChatResponse
from app.conversations import router as conversations_router
from app.users import router as users_router
from app.history import router as history_router
from app.documents import router as documents_router
from app.agent_routes import router as agent_router
from app.chat_service import run_turn

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
for router in (users_router, conversations_router, history_router, documents_router, agent_router):
    app.include_router(router)

@app.get("/")
def root():
    return {"message": "DocPilot API running", "version": "2.0.0"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user=Depends(get_current_user), credentials=Depends(bearer), db=Depends(get_db)):
    return run_turn(request, credentials, db)
