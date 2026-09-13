# Bank API schemas expose decisions and recorded outcomes without projected results.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DecisionChoice = Literal["agreement", "defense", "human_review"]
BankDecisionStatus = Literal["pending", "approved"]
RecordedOutcome = Literal["favorable", "settled", "unfavorable"]
DecisionOutcome = Literal["pending", "favorable", "settled", "unfavorable"]
AdherenceStatus = Literal["adherent", "justified", "divergent", "unavailable"]
NegotiationStatus = Literal[
    "not_applicable",
    "pending",
    "accepted",
    "refused",
    "counterproposal",
]


class JudgeChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class JudgeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    history: list[JudgeChatTurn] = Field(default_factory=list, max_length=20)


class BankOutcomeCreate(BaseModel):
    outcome: RecordedOutcome
    actual_cost: float = Field(ge=0, le=1_000_000_000)

    @model_validator(mode="after")
    def validate_actual_cost(self) -> "BankOutcomeCreate":
        if self.outcome == "favorable" and self.actual_cost != 0:
            raise ValueError("Uma defesa favorável deve registrar custo realizado de zero.")
        if self.outcome != "favorable" and self.actual_cost <= 0:
            raise ValueError("Acordo ou condenação exigem valor realizado maior que zero.")
        return self


class BankDashboardMetrics(BaseModel):
    process_count: int = Field(ge=0)
    decision_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    outcome_recorded_count: int = Field(ge=0)
    pending_outcome_count: int = Field(ge=0)
    actual_cost_total: float = Field(ge=0)
    expected_cost_total: float = Field(ge=0)
    cost_difference: float
    adherence_eligible_count: int = Field(ge=0)
    adherent_count: int = Field(ge=0)
    justified_divergence_count: int = Field(ge=0)
    divergent_count: int = Field(ge=0)
    adherence_rate: float = Field(ge=0, le=1)
    negotiation_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    refused_count: int = Field(ge=0)
    counterproposal_count: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0, le=1)


class BankDecisionItem(BaseModel):
    id: uuid.UUID
    process_id: uuid.UUID
    case_number: str
    process_title: str
    state: str
    recommendation: DecisionChoice
    model_recommendation: DecisionChoice | None
    adherence_status: AdherenceStatus
    amount: float | None
    justification: str | None
    bank_status: BankDecisionStatus
    evidence_count: int = Field(ge=0, le=6)
    claim_amount: float = Field(ge=0)
    expected_cost: float = Field(ge=0)
    outcome: DecisionOutcome
    actual_cost: float | None = Field(default=None, ge=0)
    outcome_recorded_at: datetime | None
    negotiation_status: NegotiationStatus
    negotiation_amount: float | None = Field(default=None, ge=0)
    negotiation_updated_at: datetime | None
    created_at: datetime
    bank_reviewed_at: datetime | None


class BankDashboardResponse(BaseModel):
    generated_at: datetime
    metrics: BankDashboardMetrics
    decisions: list[BankDecisionItem]
