import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DecisionChoice = Literal["agreement", "defense", "human_review"]
AdherenceStatus = Literal["adherent", "justified", "divergent"]
BankDecisionStatus = Literal["pending", "approved"]
ProjectedOutcome = Literal["favorable", "unfavorable"]


class BankDashboardMetrics(BaseModel):
    adherence_rate: float = Field(ge=0, le=1)
    estimated_savings: float
    acceptance_rate: float = Field(ge=0, le=1)
    process_count: int = Field(ge=0)
    decision_count: int = Field(ge=0)
    adherent_count: int = Field(ge=0)
    justified_count: int = Field(ge=0)
    divergent_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    favorable_count: int = Field(ge=0)
    unfavorable_count: int = Field(ge=0)
    projected_success_rate: float = Field(ge=0, le=1)
    historical_condemnation_ratio: float = Field(ge=0, le=1)
    historical_sample_size: int = Field(gt=0)
    estimated_condemnation_total: float = Field(ge=0)
    optimized_decision_cost: float = Field(ge=0)
    relative_savings: float
    average_offered_amount: float = Field(ge=0)
    average_savings_per_case: float


class BankMonthlyEffectiveness(BaseModel):
    month: str
    favorable_count: int = Field(ge=0)
    unfavorable_count: int = Field(ge=0)
    estimated_savings: float


class BankDecisionItem(BaseModel):
    id: uuid.UUID
    process_id: uuid.UUID
    case_number: str
    process_title: str
    state: str
    model_recommendation: DecisionChoice
    recommended_amount: float | None
    lawyer_recommendation: DecisionChoice
    lawyer_amount: float | None
    justification: str | None
    adherence_status: AdherenceStatus
    bank_status: BankDecisionStatus
    evidence_count: int = Field(ge=0, le=6)
    claim_amount: float = Field(ge=0)
    historical_estimated_condemnation: float = Field(ge=0)
    projected_decision_cost: float | None = Field(default=None, ge=0)
    optimized_savings: float | None
    expected_condemnation: float
    created_at: datetime
    loss_probability: float = Field(ge=0, le=1)
    projected_outcome: ProjectedOutcome | None
    projected_outcome_reason: str | None
    bank_reviewed_at: datetime | None


class BankDashboardResponse(BaseModel):
    generated_at: datetime
    metrics: BankDashboardMetrics
    monthly_effectiveness: list[BankMonthlyEffectiveness]
    decisions: list[BankDecisionItem]
