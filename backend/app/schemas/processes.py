# Process API schemas keep the lawyer workspace and persistence boundary explicit.

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.documents import canonical_process_number
from app.schemas.analysis import (
    AgreementJustificationReview,
    AgreementRange,
    DecisionJustifications,
    EvidenceInput,
)


class LegalProcessCreate(BaseModel):
    case_number: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=160)
    state: str = Field(min_length=2, max_length=2)
    sub_subject: str = Field(pattern=r"^(fraud|generic)$")
    claim_amount: float = Field(gt=0)
    evidence: EvidenceInput = Field(default_factory=EvidenceInput)
    default_question: str | None = Field(default=None, max_length=2_000)

    @field_validator("case_number")
    @classmethod
    def validate_case_number(cls, value: str) -> str:
        normalized = value.strip()
        canonical_process_number(normalized)
        return normalized

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.upper()


class LegalProcessUpdate(BaseModel):
    case_number: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"] | None = None
    claim_amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    evidence: EvidenceInput | None = None

    @field_validator("case_number")
    @classmethod
    def validate_case_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        canonical_process_number(normalized)
        return normalized

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("title")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class InferredProcessTitle(BaseModel):
    title: str = Field(min_length=3, max_length=80)


class LegalProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    state: str
    sub_subject: str
    claim_amount: float
    evidence: EvidenceInput
    default_question: str
    model_inputs_edited: bool
    is_draft: bool
    created_at: datetime
    updated_at: datetime


class ProcessFinancialRisk(BaseModel):
    loss_probability: float = Field(ge=0, le=1)
    expected_condemnation: float = Field(ge=0)
    condemnation_q10: float = Field(ge=0)
    condemnation_q50: float = Field(ge=0)
    condemnation_q90: float = Field(ge=0)
    model_disagreement: float = Field(ge=0, le=1)
    component_probabilities: dict[str, float]
    requires_model_review: bool
    model_version: str


class ProcessFinancialDecision(BaseModel):
    recommendation: Literal["agreement", "defense", "human_review"]
    risk_band: Literal["low", "medium", "high"]
    expected_defense_cost: float = Field(ge=0)
    evaluated_agreement_cost: float | None
    agreement_range: AgreementRange | None
    next_action: Literal["propose_agreement", "prepare_defense", "human_review"]
    human_review_reason: str | None


class ProcessDecisionCreate(BaseModel):
    recommendation: Literal["agreement", "defense", "human_review"]
    amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    justification: str | None = Field(default=None, max_length=2_000)

    @field_validator("justification")
    @classmethod
    def normalize_justification(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None

    @model_validator(mode="after")
    def validate_amount(self) -> "ProcessDecisionCreate":
        if self.recommendation == "agreement" and self.amount is None:
            raise ValueError("An agreement decision requires a positive amount")
        if self.recommendation != "agreement" and self.amount is not None:
            raise ValueError("Only an agreement decision accepts an amount")
        return self


class ProcessDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    process_id: uuid.UUID
    recommendation: Literal["agreement", "defense", "human_review"]
    amount: float | None
    justification: str | None
    bank_status: Literal["pending", "approved"]
    bank_reviewed_at: datetime | None
    projected_outcome: Literal["favorable", "unfavorable"] | None
    projected_outcome_reason: str | None
    model_snapshot: dict[str, Any]
    created_at: datetime


class ProcessFinancialOverviewResponse(BaseModel):
    case_number: str
    title: str
    updated_at: datetime
    input_source: Literal["workbook_row", "process_registry"]
    workbook_path: str
    source_rows: dict[str, int]
    state: str
    sub_subject: Literal["fraud", "generic"]
    claim_amount: float = Field(gt=0)
    evidence: EvidenceInput
    evidence_score: float = Field(ge=0, le=1)
    risk: ProcessFinancialRisk | None
    decision: ProcessFinancialDecision | None
    latest_decision: ProcessDecisionResponse | None
    agreement_justification_review: AgreementJustificationReview | None = None
    decision_justifications: DecisionJustifications | None = None


class EvidenceMatrixCitation(BaseModel):
    document_path: str = Field(min_length=1)
    document_name: str = Field(min_length=1)
    page: int = Field(ge=1)


class EvidenceMatrixEntry(BaseModel):
    question: Literal[
        "Houve contratação?",
        "O crédito entrou na conta?",
        "Os descontos batem?",
        "A assinatura é compatível?",
    ]
    status: Literal["supported", "contradicted", "no_evidence"]
    explanation: str = Field(min_length=1, max_length=600)
    citations: list[EvidenceMatrixCitation] = Field(default_factory=list, max_length=3)


class EvidenceMatrixResponse(BaseModel):
    entries: list[EvidenceMatrixEntry] = Field(min_length=4, max_length=4)
