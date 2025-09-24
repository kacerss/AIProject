from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class DocumentStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Citation(BaseModel):
    doc_name: str
    page: int
    score: float


class Document(BaseModel):
    id: Optional[int] = None
    name: str
    bytes: int = 0
    pages: int = 0
    sha256: str
    status: DocumentStatus = DocumentStatus.NEW
    created_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class Session(BaseModel):
    id: Optional[int] = None
    title: str
    created_at: Optional[datetime] = None


class Message(BaseModel):
    id: Optional[int] = None
    session_id: int
    role: MessageRole
    content: str
    citations: Optional[List[Citation]] = None
    created_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class Page(BaseModel):
    id: Optional[int] = None
    doc_id: int
    page_no: int
    text: str


# Request/Response models for API endpoints
class ChatRequest(BaseModel):
    session_id: int
    message: str


class ChatResponse(BaseModel):
    message: str
    citations: List[Citation]


class DocumentUploadResponse(BaseModel):
    document_id: int
    status: str
    message: str


class SessionCreateRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    message_count: int = 0
