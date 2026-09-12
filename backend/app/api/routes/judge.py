import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.documents import EvidenceDocumentType, UploadedDocumentResponse
from app.schemas.judge import (
    DocumentCatalogResponse,
    JudgeReviewRequest,
    JudgeReviewResponse,
    ProcessDataRecord,
    ProcessDataReference,
)
from app.services.judge import JudgeExecutionError, JudgeOutputError, judge_service

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/documents", response_model=DocumentCatalogResponse, tags=["documents"])
def list_documents() -> DocumentCatalogResponse:
    try:
        return judge_service.catalog()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/documents/uploads",
    response_model=UploadedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF or CSV document, maximum 20 MiB")],
    document_type: Annotated[EvidenceDocumentType, Form()],
) -> UploadedDocumentResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload filename is required",
        )
    try:
        return await asyncio.to_thread(
            judge_service.upload_document,
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


@router.get(
    "/process-data/{process_number}",
    response_model=ProcessDataRecord,
    tags=["documents"],
)
def get_process_data(
    process_number: str,
    workbook_path: Annotated[
        str,
        Query(min_length=1, max_length=512),
    ] = "datasets/Hackaton_Enter_Base_Candidatos.xlsx",
) -> ProcessDataRecord:
    try:
        return judge_service.process_data(
            ProcessDataReference(
                workbook_path=workbook_path,
                process_number=process_number,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post("/judge/reviews", response_model=JudgeReviewResponse, tags=["judge"])
async def create_judge_review(
    payload: JudgeReviewRequest,
    session: SessionDependency,
) -> JudgeReviewResponse:
    try:
        return await judge_service.review(session, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (JudgeExecutionError, JudgeOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
