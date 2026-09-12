import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatSessionResponse,
    ChatStreamRequest,
    ProcessDocumentListResponse,
    ProcessDocumentResponse,
)
from app.schemas.documents import EvidenceDocumentType
from app.services.chat import chat_service
from app.services.process_documents import process_document_service

router = APIRouter(prefix="/processes/{case_number}")
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/documents",
    response_model=ProcessDocumentListResponse,
    tags=["process documents"],
)
async def list_process_documents(
    case_number: str,
    session: SessionDependency,
) -> ProcessDocumentListResponse:
    try:
        return await process_document_service.list(session, case_number)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

@router.get(
    "/documents/content",
    response_class=FileResponse,
    tags=["process documents"],
)
async def get_process_document_content(
    case_number: str,
    document_path: str,
    session: SessionDependency,
) -> FileResponse:
    try:
        path, media_type = await process_document_service.resolve_content(
            session,
            case_number,
            document_path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path, media_type=media_type)


@router.post(
    "/documents",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["process documents"],
)
async def upload_process_document(
    case_number: str,
    session: SessionDependency,
    file: Annotated[UploadFile, File(description="PDF or CSV document, maximum 20 MiB")],
    document_type: Annotated[EvidenceDocumentType, Form()],
) -> ProcessDocumentResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload filename is required",
        )
    try:
        return await process_document_service.upload(
            session,
            case_number,
            file.filename,
            file.file,
            document_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["process documents"],
)
async def delete_process_document(
    case_number: str,
    document_id: uuid.UUID,
    session: SessionDependency,
) -> Response:
    try:
        deleted = await process_document_service.delete(session, case_number, document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/chats",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["process chat"],
)
async def create_process_chat(
    case_number: str,
    session: SessionDependency,
) -> ChatSessionResponse:
    try:
        return await chat_service.create_session(session, case_number)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/chats",
    response_model=list[ChatSessionResponse],
    tags=["process chat"],
)
async def list_process_chats(
    case_number: str,
    session: SessionDependency,
) -> list[ChatSessionResponse]:
    try:
        return await chat_service.list_sessions(session, case_number)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/chats/{chat_id}",
    response_model=ChatHistoryResponse,
    tags=["process chat"],
)
async def get_process_chat(
    case_number: str,
    chat_id: uuid.UUID,
    session: SessionDependency,
) -> ChatHistoryResponse:
    try:
        return await chat_service.history(session, case_number, chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/chats/{chat_id}/messages/stream",
    response_class=EventSourceResponse,
    tags=["process chat"],
)
async def stream_process_chat_message(
    case_number: str,
    chat_id: uuid.UUID,
    payload: ChatStreamRequest,
    session: SessionDependency,
) -> AsyncIterator[ServerSentEvent]:
    try:
        context = await chat_service.prepare_stream(session, case_number, chat_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    async for stream_event in chat_service.stream(context):
        yield stream_event
