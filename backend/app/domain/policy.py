from dataclasses import dataclass
from typing import Literal

from app.schemas.analysis import AgreementRange, AnalysisRequest


@dataclass(frozen=True)
class PolicyDecision:
    recommendation: Literal["agreement", "defense", "human_review"]
    risk_band: Literal["low", "medium", "high"]
    expected_defense_cost: float
    evaluated_agreement_cost: float | None
    agreement_cheaper: bool | None
    agreement_range: AgreementRange | None
    next_action: Literal["propose_agreement", "prepare_defense", "human_review"]
    human_review_reason: str | None


class SettlementPolicy:
    version = "decision-tree-2026-09-12"
    litigation_cost = 1_500.0
    low_risk_threshold = 0.40
    high_risk_threshold = 0.60

    def evaluate(
        self,
        request: AnalysisRequest,
        *,
        loss_probability: float,
        expected_condemnation: float,
    ) -> PolicyDecision:
        expected_defense_cost = round(
            loss_probability * expected_condemnation + self.litigation_cost,
            2,
        )
        if loss_probability < self.low_risk_threshold:
            return PolicyDecision(
                recommendation="defense",
                risk_band="low",
                expected_defense_cost=expected_defense_cost,
                evaluated_agreement_cost=None,
                agreement_cheaper=None,
                agreement_range=None,
                next_action="prepare_defense",
                human_review_reason=None,
            )
        if loss_probability <= self.high_risk_threshold:
            return PolicyDecision(
                recommendation="human_review",
                risk_band="medium",
                expected_defense_cost=expected_defense_cost,
                evaluated_agreement_cost=None,
                agreement_cheaper=None,
                agreement_range=None,
                next_action="human_review",
                human_review_reason=(
                    "Probabilidade de perda entre 40% e 60%; decisão automática bloqueada."
                ),
            )

        claim = request.claim_amount
        ceiling = min(claim * 0.70, max(claim * 0.30, expected_defense_cost))
        target = min(ceiling, max(claim * 0.30, expected_defense_cost * 0.65))
        opening = min(target, max(claim * 0.20, target * 0.85))
        agreement_range = AgreementRange(
            opening=round(opening, 2),
            target=round(target, 2),
            ceiling=round(ceiling, 2),
        )
        agreement_cheaper = agreement_range.target < expected_defense_cost
        return PolicyDecision(
            recommendation="agreement" if agreement_cheaper else "defense",
            risk_band="high",
            expected_defense_cost=expected_defense_cost,
            evaluated_agreement_cost=agreement_range.target,
            agreement_cheaper=agreement_cheaper,
            agreement_range=agreement_range if agreement_cheaper else None,
            next_action="propose_agreement" if agreement_cheaper else "prepare_defense",
            human_review_reason=None,
        )
