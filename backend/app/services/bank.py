import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LegalProcess, ProcessDecision
from app.schemas.bank import (
    BankDashboardMetrics,
    BankDashboardResponse,
    BankDecisionItem,
    BankMonthlyEffectiveness,
)

HISTORICAL_PARTIAL_PROCEDENCE_SAMPLE = 12_248
HISTORICAL_CONDEMNATION_RATIO = 0.6223546701502286


class BankDashboardService:
    @staticmethod
    def _number(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _currency(value: float) -> str:
        formatted = f"{value:,.2f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @classmethod
    def _decision_economics(
        cls,
        decision: ProcessDecision,
        snapshot: dict[str, Any],
    ) -> tuple[float, float | None, float | None]:
        claim_amount = cls._number(snapshot.get("claim_amount"))
        estimated_condemnation = round(
            claim_amount * HISTORICAL_CONDEMNATION_RATIO,
            2,
        )
        if decision.bank_status != "approved":
            return estimated_condemnation, None, None

        if decision.recommendation == "agreement" and decision.amount is not None:
            decision_cost = cls._number(decision.amount)
        elif (
            decision.recommendation == "defense"
            and decision.projected_outcome == "favorable"
        ):
            decision_cost = 0.0
        else:
            decision_cost = estimated_condemnation
        return (
            estimated_condemnation,
            round(decision_cost, 2),
            round(estimated_condemnation - decision_cost, 2),
        )

    @classmethod
    def _project_outcome(cls, decision: ProcessDecision) -> tuple[str, str]:
        snapshot: dict[str, Any] = decision.model_snapshot or {}
        risk = snapshot.get("risk") or {}
        loss_probability = min(max(cls._number(risk.get("loss_probability")), 0), 1)
        expected_condemnation = cls._number(risk.get("expected_condemnation"))

        if decision.recommendation == "defense":
            success_probability = 1 - loss_probability
            outcome = "favorable" if success_probability >= 0.5 else "unfavorable"
            reason = (
                "A defesa tem probabilidade projetada de êxito de "
                f"{success_probability:.1%}, calculada a partir do risco de perda salvo."
            )
            return outcome, reason.replace(".", ",", 1)

        if decision.recommendation == "agreement" and decision.amount is not None:
            amount = cls._number(decision.amount)
            difference = expected_condemnation - amount
            if difference >= 0:
                return (
                    "favorable",
                    "O acordo fica R$ "
                    f"{cls._currency(difference)} abaixo da exposição estimada.",
                )
            return (
                "unfavorable",
                "O acordo excede a exposição estimada em R$ "
                f"{cls._currency(abs(difference))}.",
            )

        return (
            "unfavorable",
            "A revisão humana não definiu acordo ou defesa para execução operacional.",
        )

    def _item(self, decision: ProcessDecision, process: LegalProcess) -> BankDecisionItem:
        snapshot: dict[str, Any] = decision.model_snapshot or {}
        model_decision = snapshot.get("decision") or {}
        risk = snapshot.get("risk") or {}
        evidence = snapshot.get("evidence") or {}
        model_recommendation = model_decision.get("recommendation", "human_review")
        agreement_range = model_decision.get("agreement_range") or {}
        recommended_amount = agreement_range.get("target")
        justification = decision.justification.strip() if decision.justification else None
        (
            historical_estimated_condemnation,
            projected_decision_cost,
            optimized_savings,
        ) = self._decision_economics(decision, snapshot)

        if decision.recommendation == model_recommendation:
            adherence_status = "adherent"
        elif justification:
            adherence_status = "justified"
        else:
            adherence_status = "divergent"

        return BankDecisionItem(
            id=decision.id,
            process_id=process.id,
            case_number=process.case_number,
            process_title=process.title,
            state=process.state,
            model_recommendation=model_recommendation,
            recommended_amount=(
                self._number(recommended_amount) if recommended_amount is not None else None
            ),
            lawyer_recommendation=decision.recommendation,
            lawyer_amount=(self._number(decision.amount) if decision.amount is not None else None),
            justification=justification,
            adherence_status=adherence_status,
            bank_status=decision.bank_status,
            evidence_count=sum(bool(value) for value in evidence.values()),
            claim_amount=self._number(snapshot.get("claim_amount")),
            historical_estimated_condemnation=historical_estimated_condemnation,
            projected_decision_cost=projected_decision_cost,
            optimized_savings=optimized_savings,
            expected_condemnation=self._number(risk.get("expected_condemnation")),
            loss_probability=min(
                max(self._number(risk.get("loss_probability")), 0),
                1,
            ),
            projected_outcome=decision.projected_outcome,
            projected_outcome_reason=decision.projected_outcome_reason,
            created_at=decision.created_at,
            bank_reviewed_at=decision.bank_reviewed_at,
        )

    @staticmethod
    def _estimated_savings(item: BankDecisionItem) -> float:
        return item.optimized_savings or 0.0

    async def _latest_items(self, session: AsyncSession) -> list[BankDecisionItem]:
        rank = func.row_number().over(
            partition_by=ProcessDecision.process_id,
            order_by=(ProcessDecision.created_at.desc(), ProcessDecision.id.desc()),
        ).label("decision_rank")
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
        decision_count = len(items)
        adherent_count = sum(item.adherence_status == "adherent" for item in items)
        justified_count = sum(item.adherence_status == "justified" for item in items)
        divergent_count = sum(item.adherence_status == "divergent" for item in items)
        approved_items = [item for item in items if item.bank_status == "approved"]
        approved_count = len(approved_items)
        favorable_count = sum(
            item.projected_outcome == "favorable" for item in approved_items
        )
        unfavorable_count = sum(
            item.projected_outcome == "unfavorable" for item in approved_items
        )
        outcome_count = favorable_count + unfavorable_count
        estimated_condemnation_total = sum(
            item.historical_estimated_condemnation for item in approved_items
        )
        optimized_decision_cost = sum(
            item.projected_decision_cost or 0.0 for item in approved_items
        )
        accepted_agreements = [
            item
            for item in approved_items
            if item.lawyer_recommendation == "agreement"
        ]
        estimated_savings = sum(self._estimated_savings(item) for item in approved_items)
        offered_amounts = [
            item.lawyer_amount
            for item in approved_items
            if item.lawyer_recommendation == "agreement" and item.lawyer_amount is not None
        ]

        effectiveness_by_month: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"favorable_count": 0, "unfavorable_count": 0, "estimated_savings": 0.0}
        )
        for item in approved_items:
            month = item.bank_reviewed_at or item.created_at
            bucket = effectiveness_by_month[month.strftime("%Y-%m")]
            if item.projected_outcome == "favorable":
                bucket["favorable_count"] += 1
            elif item.projected_outcome == "unfavorable":
                bucket["unfavorable_count"] += 1
            bucket["estimated_savings"] += self._estimated_savings(item)

        return BankDashboardResponse(
            generated_at=datetime.now(UTC),
            metrics=BankDashboardMetrics(
                adherence_rate=adherent_count / decision_count if decision_count else 0,
                estimated_savings=estimated_savings,
                acceptance_rate=(
                    len(accepted_agreements) / approved_count if approved_count else 0
                ),
                process_count=int(process_count or 0),
                decision_count=decision_count,
                adherent_count=adherent_count,
                justified_count=justified_count,
                divergent_count=divergent_count,
                approved_count=approved_count,
                favorable_count=favorable_count,
                unfavorable_count=unfavorable_count,
                projected_success_rate=(
                    favorable_count / outcome_count if outcome_count else 0
                ),
                historical_condemnation_ratio=HISTORICAL_CONDEMNATION_RATIO,
                historical_sample_size=HISTORICAL_PARTIAL_PROCEDENCE_SAMPLE,
                estimated_condemnation_total=estimated_condemnation_total,
                optimized_decision_cost=optimized_decision_cost,
                relative_savings=(
                    estimated_savings / estimated_condemnation_total
                    if estimated_condemnation_total
                    else 0
                ),
                average_offered_amount=(
                    sum(offered_amounts) / len(offered_amounts) if offered_amounts else 0
                ),
                average_savings_per_case=(
                    estimated_savings / outcome_count if outcome_count else 0
                ),
            ),
            monthly_effectiveness=[
                BankMonthlyEffectiveness(
                    month=month,
                    favorable_count=int(values["favorable_count"]),
                    unfavorable_count=int(values["unfavorable_count"]),
                    estimated_savings=float(values["estimated_savings"]),
                )
                for month, values in sorted(effectiveness_by_month.items())
            ],
            decisions=items,
        )

    async def approve_decision(
        self,
        session: AsyncSession,
        decision_id: uuid.UUID,
    ) -> BankDecisionItem:
        decision = await session.get(ProcessDecision, decision_id)
        if decision is None:
            raise LookupError("decision not found")
        process = await session.get(LegalProcess, decision.process_id)
        if process is None:
            raise LookupError("process not found")

        outcome, reason = self._project_outcome(decision)
        if decision.bank_status != "approved":
            decision.bank_status = "approved"
            decision.bank_reviewed_at = datetime.now(UTC)
        decision.projected_outcome = outcome
        decision.projected_outcome_reason = reason
        await session.commit()
        await session.refresh(decision)
        return self._item(decision, process)


bank_dashboard_service = BankDashboardService()
