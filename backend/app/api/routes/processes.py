from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.processes import LegalProcessCreate, LegalProcessResponse
from app.services.processes import legal_process_service

router = APIRouter(prefix="/processes", tags=["processes"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[LegalProcessResponse])
async def list_processes(session: SessionDependency) -> list[LegalProcessResponse]:
    return await legal_process_service.list(session)


@router.post(
    "/drafts",
    response_model=LegalProcessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_process(session: SessionDependency) -> LegalProcessResponse:
    process = await legal_process_service.create_draft(session)
    return LegalProcessResponse.model_validate(process)


@router.post("", response_model=LegalProcessResponse, status_code=status.HTTP_201_CREATED)
async def create_process(
    payload: LegalProcessCreate,
    session: SessionDependency,
) -> LegalProcessResponse:
    try:
        process = await legal_process_service.upsert(session, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return LegalProcessResponse.model_validate(process)
