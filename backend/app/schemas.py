from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

Role = Literal["employee", "hr", "admin"]
KnowledgeBase = Literal["company", "paper"]

class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Credentials(Request):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

class Registration(Credentials):
    password: str = Field(min_length=8, max_length=256)

class RoleUpdateRequest(Request):
    role: Role

class ConversationCreate(Request):
    title: str = Field(default="新会话", min_length=1, max_length=200)
    knowledge_base: KnowledgeBase = "company"

class ConversationUpdate(Request):
    title: str = Field(min_length=1, max_length=200)

class ChatRequest(Request):
    question: str = Field(min_length=1, max_length=10000)
    conversation_id: int = Field(gt=0)

class UserResponse(BaseModel):
    user_id: int
    username: str
    role: Role

class RegistrationResponse(UserResponse):
    message: str

class LoginResponse(UserResponse):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int

class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int

class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    knowledge_base: KnowledgeBase
    created_time: datetime | None
    updated_time: datetime | None

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: Literal["user", "assistant"]
    content: str
    sources: list[dict]
    created_time: datetime | None

class HistoryResponse(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    question: str
    answer: str
    sources: list[dict]
    created_time: datetime | None

class DocumentResponse(BaseModel):
    filename: str
    chunks: int
    role: Role
    knowledge_base: KnowledgeBase

class UploadResponse(DocumentResponse):
    message: str

class DocumentContentResponse(BaseModel):
    filename: str
    knowledge_base: KnowledgeBase
    chunks: list[dict]

class DocumentRoleResponse(BaseModel):
    filename: str
    role: Role

class ChatResponse(BaseModel):
    conversation_id: int
    question: str
    answer: str
    sources: list[dict]
    timings: dict[str, float]
