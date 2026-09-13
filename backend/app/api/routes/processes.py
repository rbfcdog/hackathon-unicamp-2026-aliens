from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.processes import (
    LegalProcessCreate,
    LegalProcessResponse,
    LegalProcessUpdate,
    ProcessDecisionCreate,
    ProcessDecisionResponse,
    ProcessFinancialOverviewResponse,
)
from app.services.processes import legal_process_service

router = APIRouter(prefix="/processes", tags=["processes"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[LegalProcessResponse])
async def list_processes(session: SessionDependency) -> list[LegalProcessResponse]:
    return await legal_process_service.list(session)


@router.get(
    "/{case_number}/financial-overview",
    response_model=ProcessFinancialOverviewResponse,
)
async def get_financial_overview(
    case_number: str,
    session: SessionDependency,
) -> ProcessFinancialOverviewResponse:
    try:
        return await legal_process_service.financial_overview(session, case_number)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.patch("/{case_number}", response_model=LegalProcessResponse)
async def update_process(
    case_number: str,
    payload: LegalProcessUpdate,
    session: SessionDependency,
) -> LegalProcessResponse:
    try:
        process = await legal_process_service.update(session, case_number, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return LegalProcessResponse.model_validate(process)


@router.post("/{case_number}/infer-title", response_model=LegalProcessResponse)
async def infer_process_title(
    case_number: str,
    session: SessionDependency,
) -> LegalProcessResponse:
    try:
        process = await legal_process_service.infer_title(session, case_number)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível sugerir o nome do processo",
        ) from exc
    return LegalProcessResponse.model_validate(process)


@router.post(
    "/{case_number}/decisions",
    response_model=ProcessDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_process_decision(
    case_number: str,
    payload: ProcessDecisionCreate,
    session: SessionDependency,
) -> ProcessDecisionResponse:
    try:
        return await legal_process_service.submit_decision(session, case_number, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{case_number}/decisions/latest",
    response_model=ProcessDecisionResponse | None,
)
async def get_latest_process_decision(
    case_number: str,
    session: SessionDependency,
) -> ProcessDecisionResponse | None:
    process = await legal_process_service.get_by_case_number(session, case_number)
    if process is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )
    return await legal_process_service.latest_decision(session, process.id)


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
