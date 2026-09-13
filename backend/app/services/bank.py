# Bank dashboard logic compares approved decisions only with recorded case outcomes.

import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LegalProcess, ProcessDecision
from app.schemas.bank import (
    BankDashboardMetrics,
    BankDashboardResponse,
    BankDecisionItem,
)
from app.schemas.documents import DocumentReference
from app.schemas.judge import JudgeReviewRequest, JudgeReviewResponse
from app.services.judge import judge_service
from app.services.process_documents import process_document_service


class BankDashboardService:
    def __init__(self) -> None:
        self._judge_reviews: dict[uuid.UUID, JudgeReviewResponse] = {}
        self._judge_review_locks: dict[uuid.UUID, asyncio.Lock] = {}

    @staticmethod
    def _number(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
    @staticmethod
    def _model_recommendation(snapshot: dict[str, object]) -> str | None:
        decision = snapshot.get("decision")
        if not isinstance(decision, dict):
            return None
        recommendation = decision.get("recommendation")
        if recommendation in {"agreement", "defense", "human_review"}:
            return str(recommendation)
        return None

    @classmethod
    def _adherence_status(
        cls,
        decision: ProcessDecision,
        snapshot: dict[str, object],
    ) -> str:
        model_recommendation = cls._model_recommendation(snapshot)
        if model_recommendation is None:
            return "unavailable"
        if decision.recommendation == model_recommendation:
            return "adherent"
        if decision.justification and decision.justification.strip():
            return "justified"
        return "divergent"

    @classmethod
    def _simulate_agreement_negotiation(cls, decision: ProcessDecision) -> None:
        if decision.recommendation != "agreement":
            decision.negotiation_status = "not_applicable"
            return
        snapshot = decision.model_snapshot or {}
        policy_decision = snapshot.get("decision")
        agreement_range = (
            policy_decision.get("agreement_range")
            if isinstance(policy_decision, dict)
            else None
        )
        agreement_range = agreement_range if isinstance(agreement_range, dict) else {}
        offer = cls._number(decision.amount)
        opening = cls._number(agreement_range.get("opening"))
        target = cls._number(agreement_range.get("target"))
        ceiling = cls._number(agreement_range.get("ceiling"))

        if target <= 0 or offer >= target:
            decision.negotiation_status = "accepted"
            decision.negotiation_amount = Decimal(str(offer))
        elif opening <= 0 or offer >= opening:
            counterproposal = min(
                ceiling or target,
                max(target, round(offer * 1.15, 2)),
            )
            decision.negotiation_status = "counterproposal"
            decision.negotiation_amount = Decimal(str(counterproposal))
        else:
            decision.negotiation_status = "refused"
            decision.negotiation_amount = None
        decision.negotiation_updated_at = datetime.now(UTC)

    def _item(self, decision: ProcessDecision, process: LegalProcess) -> BankDecisionItem:
        snapshot = decision.model_snapshot or {}
        risk = snapshot.get("risk") or {}
        evidence = snapshot.get("evidence") or {}
        return BankDecisionItem(
            id=decision.id,
            process_id=process.id,
            case_number=process.case_number,
            process_title=process.title,
            state=process.state,
            recommendation=decision.recommendation,
            model_recommendation=self._model_recommendation(snapshot),
            adherence_status=self._adherence_status(decision, snapshot),
            amount=(self._number(decision.amount) if decision.amount is not None else None),
            justification=decision.justification.strip() if decision.justification else None,
            bank_status=decision.bank_status,
            evidence_count=sum(bool(value) for value in evidence.values()),
            claim_amount=self._number(snapshot.get("claim_amount")),
            expected_cost=self._number(risk.get("expected_condemnation")),
            outcome=decision.outcome,
            actual_cost=(
                self._number(decision.actual_cost) if decision.actual_cost is not None else None
            ),
            outcome_recorded_at=decision.outcome_recorded_at,
            negotiation_status=decision.negotiation_status,
            negotiation_amount=(
                self._number(decision.negotiation_amount)
                if decision.negotiation_amount is not None
                else None
            ),
            negotiation_updated_at=decision.negotiation_updated_at,
            created_at=decision.created_at,
            bank_reviewed_at=decision.bank_reviewed_at,
        )

    async def _latest_items(self, session: AsyncSession) -> list[BankDecisionItem]:
        rank = (
            func.row_number()
            .over(
                partition_by=ProcessDecision.process_id,
                order_by=(ProcessDecision.created_at.desc(), ProcessDecision.id.desc()),
            )
            .label("decision_rank")
        )
        ranked = select(ProcessDecision.id.label("decision_id"), rank).subquery()
        result = await session.execute(
            select(ProcessDecision, LegalProcess)
            .join(ranked, ranked.c.decision_id == ProcessDecision.id)
            .join(LegalProcess, LegalProcess.id == ProcessDecision.process_id)
            .where(ranked.c.decision_rank == 1)
            .order_by(ProcessDecision.created_at.desc(), ProcessDecision.id.desc())
        )
        return [self._item(decision, process) for decision, process in result.all()]

    async def dashboard(self, session: AsyncSession) -> BankDashboardResponse:
        items = await self._latest_items(session)
        process_count = await session.scalar(
            select(func.count(LegalProcess.id)).where(
                ~LegalProcess.case_number.startswith("RASCUNHO-")
            )
        )
        approved_items = [item for item in items if item.bank_status == "approved"]
        recorded_items = [item for item in approved_items if item.outcome != "pending"]
        adherence_items = [
            item for item in items if item.adherence_status != "unavailable"
        ]
        adherent_count = sum(
            item.adherence_status == "adherent" for item in adherence_items
        )
        justified_count = sum(
            item.adherence_status == "justified" for item in adherence_items
        )
        divergent_count = sum(
            item.adherence_status == "divergent" for item in adherence_items
        )
        negotiation_items = [
            item
            for item in approved_items
            if item.recommendation == "agreement"
            and item.negotiation_status in {"accepted", "refused", "counterproposal"}
        ]
        accepted_count = sum(
            item.negotiation_status == "accepted" for item in negotiation_items
        )
        refused_count = sum(
            item.negotiation_status == "refused" for item in negotiation_items
        )
        counterproposal_count = sum(
            item.negotiation_status == "counterproposal" for item in negotiation_items
        )
        decided_negotiations = accepted_count + refused_count
        actual_cost_total = round(
            sum(item.actual_cost or 0.0 for item in recorded_items),
            2,
        )
        expected_cost_total = round(
            sum(item.expected_cost for item in recorded_items),
            2,
        )
        return BankDashboardResponse(
            generated_at=datetime.now(UTC),
            metrics=BankDashboardMetrics(
                process_count=int(process_count or 0),
                decision_count=len(items),
                approved_count=len(approved_items),
                outcome_recorded_count=len(recorded_items),
                pending_outcome_count=len(approved_items) - len(recorded_items),
                actual_cost_total=actual_cost_total,
                expected_cost_total=expected_cost_total,
                cost_difference=round(actual_cost_total - expected_cost_total, 2),
                adherence_eligible_count=len(adherence_items),
                adherent_count=adherent_count,
                justified_divergence_count=justified_count,
                divergent_count=divergent_count,
                adherence_rate=(
                    round(adherent_count / len(adherence_items), 4)
                    if adherence_items
                    else 0
                ),
                negotiation_count=len(negotiation_items),
                accepted_count=accepted_count,
                refused_count=refused_count,
                counterproposal_count=counterproposal_count,
                acceptance_rate=(
                    round(accepted_count / decided_negotiations, 4)
                    if decided_negotiations
                    else 0
                ),
            ),
            decisions=items,
        )

    async def _decision_and_process(
        self,
        session: AsyncSession,
        decision_id: uuid.UUID,
    ) -> tuple[ProcessDecision, LegalProcess]:
        decision = await session.get(ProcessDecision, decision_id)
        if decision is None:
            raise LookupError("decision not found")
        process = await session.get(LegalProcess, decision.process_id)
        if process is None:
            raise LookupError("process not found")
        return decision, process

    @staticmethod
    def _judge_question(decision: ProcessDecision) -> str:
        payload = {
            "decision_submitted": decision.recommendation,
            "agreement_amount": (float(decision.amount) if decision.amount is not None else None),
            "decision_rationale": decision.justification,
            "case_context": decision.model_snapshot or {},
        }
        return (
            "Revise, como juiz independente, se a decisão operacional submetida "
            "pelo responsável pelo processo é compatível com todos os documentos "
            "autorizados e com o racional abaixo. Leia obrigatoriamente cada "
            "documento, trate lacunas como insuficiência de prova e explique se há "
            "suporte, contradição ou ausência de prova para a recomendação. Não "
            "aprove nem execute a decisão: produza apenas o parecer estruturado. "
            "Use linguagem jurídica clara, sem mencionar sistemas, modelos, "
            "automatizações ou inteligência artificial.\n\n"
            f"Decisão submetida:\n{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    async def review_decision(
        self,
        session: AsyncSession,
        decision_id: uuid.UUID,
    ) -> JudgeReviewResponse:
        cached = self._judge_reviews.get(decision_id)
        if cached is not None:
            return cached

        review_lock = self._judge_review_locks.setdefault(decision_id, asyncio.Lock())
        async with review_lock:
            cached = self._judge_reviews.get(decision_id)
            if cached is not None:
                return cached

            decision, process = await self._decision_and_process(session, decision_id)
            documents = await process_document_service.list(session, process.case_number)
            if not documents.documents:
                raise ValueError(
                    "Envie ao menos um documento do processo para a revisão independente."
                )
            request = JudgeReviewRequest(
                case_number=process.case_number,
                question=self._judge_question(decision),
                documents=[
                    DocumentReference(
                        path=document.path,
                        document_type=document.document_type,
                    )
                    for document in documents.documents
                ],
            )
            review = await judge_service.review(session, request)
            self._judge_reviews[decision_id] = review
            return review

    async def approve_decision(
        self,
        session: AsyncSession,
        decision_id: uuid.UUID,
    ) -> BankDecisionItem:
        decision, process = await self._decision_and_process(session, decision_id)
        await self.review_decision(session, decision_id)
        changed = False
        if decision.bank_status != "approved":
            decision.bank_status = "approved"
            decision.bank_reviewed_at = datetime.now(UTC)
            changed = True
        if decision.recommendation == "agreement" and decision.negotiation_status == "pending":
            self._simulate_agreement_negotiation(decision)
            changed = True
        if changed:
            await session.commit()
            await session.refresh(decision)
        return self._item(decision, process)

    async def record_outcome(
        self,
        session: AsyncSession,
        decision_id: uuid.UUID,
        outcome: str,
        actual_cost: float,
    ) -> BankDecisionItem:
        decision, process = await self._decision_and_process(session, decision_id)
        if decision.bank_status != "approved":
            raise ValueError("Encaminhe a decisão antes de registrar o resultado.")
        decision.outcome = outcome
        decision.actual_cost = Decimal(str(actual_cost))
        decision.outcome_recorded_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(decision)
        return self._item(decision, process)


bank_dashboard_service = BankDashboardService()
