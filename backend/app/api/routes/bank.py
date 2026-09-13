import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.bank import BankDashboardResponse, BankDecisionItem
from app.services.bank import bank_dashboard_service

router = APIRouter(prefix="/bank", tags=["bank"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/dashboard", response_model=BankDashboardResponse)
async def get_bank_dashboard(session: SessionDependency) -> BankDashboardResponse:
    return await bank_dashboard_service.dashboard(session)


@router.post(
    "/decisions/{decision_id}/approve",
    response_model=BankDecisionItem,
)
async def approve_bank_decision(
    decision_id: uuid.UUID,
    session: SessionDependency,
) -> BankDecisionItem:
    try:
        return await bank_dashboard_service.approve_decision(session, decision_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        ) from exc
