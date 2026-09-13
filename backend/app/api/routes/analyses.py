import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services import analysis_service
from app.services.analysis import AnalysisExecutionError, AnalysisInputError

router = APIRouter(prefix="/analyses", tags=["analyses"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: AnalysisRequest,
    session: SessionDependency,
) -> AnalysisResponse:
    try:
        return await analysis_service.create(session, payload)
    except AnalysisInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except AnalysisExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/latest", response_model=AnalysisResponse | None)
async def get_latest_analysis(
    case_number: Annotated[str, Query(min_length=1, max_length=64)],
    session: SessionDependency,
) -> AnalysisResponse | None:
    return await analysis_service.latest_for_case(session, case_number)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: uuid.UUID,
    session: SessionDependency,
) -> AnalysisResponse:
    analysis = await analysis_service.get(session, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="analysis not found")
    return analysis
