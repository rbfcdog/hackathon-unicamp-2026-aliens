import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.documents import DocumentKind, DocumentPath, EvidenceDocumentType


class ProcessDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None
    case_number: str
    path: DocumentPath
    original_filename: str
    document_type: EvidenceDocumentType
    kind: DocumentKind
    source: Literal["bundled", "upload"]
    size_bytes: int = Field(gt=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime | None


class ProcessDocumentListResponse(BaseModel):
    case_number: str
    documents: list[ProcessDocumentResponse]


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    document_paths: list[DocumentPath]
    trace_id: uuid.UUID | None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
