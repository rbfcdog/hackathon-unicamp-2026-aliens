# Bank routes expose independent reviews, approved decisions, and recorded results.

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.bank import (
    BankDashboardResponse,
    BankDecisionItem,
    BankOutcomeCreate,
    JudgeChatRequest,
)
from app.schemas.judge import JudgeReviewResponse
from app.services.bank import bank_dashboard_service
from app.services.judge import JudgeExecutionError, JudgeOutputError
from app.services.judge_discussion import judge_discussion_service

router = APIRouter(prefix="/bank", tags=["bank"])
logger = logging.getLogger(__name__)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/dashboard", response_model=BankDashboardResponse)
async def get_bank_dashboard(session: SessionDependency) -> BankDashboardResponse:
    return await bank_dashboard_service.dashboard(session)


@router.post(
    "/decisions/{decision_id}/judge-review",
    response_model=JudgeReviewResponse,
)
async def review_bank_decision(
    decision_id: uuid.UUID,
    session: SessionDependency,
) -> JudgeReviewResponse:
    try:
        return await bank_dashboard_service.review_decision(session, decision_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (JudgeExecutionError, JudgeOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A revisão independente falhou; a decisão não foi encaminhada.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected bank judge review failure")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível concluir a revisão independente. Tente novamente.",
        ) from exc


@router.post(
    "/decisions/{decision_id}/judge-review/stream",
    response_class=EventSourceResponse,
)
async def stream_bank_decision_review(
    decision_id: uuid.UUID,
    session: SessionDependency,
) -> AsyncIterator[ServerSentEvent]:
    yield ServerSentEvent(
        event="ready",
        data={"message": "A revisão independente foi iniciada."},
    )
    review_task = asyncio.create_task(bank_dashboard_service.review_decision(session, decision_id))
    try:
        while not review_task.done():
            done, _ = await asyncio.wait({review_task}, timeout=15)
            if not done:
                yield ServerSentEvent(comment="keep-alive")
        review = await review_task
    except LookupError:
        yield ServerSentEvent(
            event="error",
            data={"message": "Decisão não encontrada."},
        )
        return
    except ValueError as exc:
        yield ServerSentEvent(
            event="error",
            data={"message": str(exc)},
        )
        return
    except (JudgeExecutionError, JudgeOutputError):
        yield ServerSentEvent(
            event="error",
            data={"message": "A revisão independente falhou."},
        )
        return
    except Exception:
        logger.exception("Unexpected bank judge review failure")
        yield ServerSentEvent(
            event="error",
            data={
                "message": ("Não foi possível concluir a revisão independente. Tente novamente.")
            },
        )
        return
    finally:
        if not review_task.done():
            review_task.cancel()
    yield ServerSentEvent(
        event="complete",
        data=review.model_dump(mode="json"),
    )


@router.post(
    "/decisions/{decision_id}/judge-chat/stream",
    response_class=EventSourceResponse,
)
async def stream_judge_discussion(
    decision_id: uuid.UUID,
    payload: JudgeChatRequest,
    session: SessionDependency,
) -> AsyncIterator[ServerSentEvent]:
    try:
        context = await judge_discussion_service.prepare(session, decision_id, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (JudgeExecutionError, JudgeOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A revisão independente falhou.",
        ) from exc
    async for event in judge_discussion_service.stream(context):
        yield event


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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (JudgeExecutionError, JudgeOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A revisão independente falhou; a decisão não foi encaminhada.",
        ) from exc


@router.post(
    "/decisions/{decision_id}/outcome",
    response_model=BankDecisionItem,
)
async def record_bank_decision_outcome(
    decision_id: uuid.UUID,
    payload: BankOutcomeCreate,
    session: SessionDependency,
) -> BankDecisionItem:
    try:
        return await bank_dashboard_service.record_outcome(
            session,
            decision_id,
            payload.outcome,
            payload.actual_cost,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
