import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.documents import DocumentPath, DocumentReference


class EvidenceInput(BaseModel):
    contract: bool = False
    bank_statement: bool = False
    credit_proof: bool = False
    dossier: bool = False
    debt_evolution: bool = False
    referenced_report: bool = False


class AnalysisRequest(BaseModel):
    case_number: str = Field(min_length=1, max_length=64)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"] | None = None
    claim_amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    evidence: EvidenceInput | None = None
    documents: list[DocumentReference] = Field(default_factory=list, max_length=20)

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validate_input_source(self) -> "AnalysisRequest":
        paths = [document.path for document in self.documents]
        if len(paths) != len(set(paths)):
            raise ValueError("documents must not contain duplicate paths")
        if self.documents:
            return self
        missing = [
            field for field in ("state", "claim_amount", "evidence") if getattr(self, field) is None
        ]
        if missing:
            raise ValueError(
                "Without documents, provide these ML input fields: " + ", ".join(missing)
            )
        if self.sub_subject is None:
            self.sub_subject = "generic"
        return self


class AgreementRange(BaseModel):
    opening: float
    target: float
    ceiling: float


class ResolvedAnalysisInput(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"]
    claim_amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    evidence: EvidenceInput
    input_source: Literal[
        "request_fields",
        "documents",
        "request_fields_and_documents",
    ]
    document_summary: str = ""


class AnalysisResult(BaseModel):
    recommendation: Literal["agreement", "defense", "human_review"]
    risk_band: Literal["low", "medium", "high"]
    evidence_score: float = Field(ge=0, le=1)
    loss_probability: float = Field(ge=0, le=1)
    expected_condemnation: float | None = Field(default=None, ge=0)
    condemnation_q10: float | None = Field(default=None, ge=0)
    condemnation_q50: float | None = Field(default=None, ge=0)
    condemnation_q90: float | None = Field(default=None, ge=0)
    model_disagreement: float = Field(ge=0, le=1)
    component_probabilities: dict[str, float]
    ensemble_weights: dict[str, float]
    requires_model_review: bool
    model_version: str = Field(min_length=1)
    expected_defense_cost: float | None = Field(default=None, ge=0)
    evaluated_agreement_cost: float | None
    agreement_cheaper: bool | None
    agreement_range: AgreementRange | None
    next_action: Literal["propose_agreement", "prepare_defense", "human_review"]
    human_review_reason: str | None
    factors_for_agreement: list[str]
    factors_for_defense: list[str]
    explanation: str
    policy_version: str
    model_inputs: ResolvedAnalysisInput | None = None
    consulted_documents: list[DocumentPath] = Field(default_factory=list)
    unreadable_documents: list[DocumentPath] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_condemnation_quantiles(self) -> "AnalysisResult":
        quantiles = (self.condemnation_q10, self.condemnation_q50, self.condemnation_q90)
        if any(value is None for value in quantiles):
            if any(value is not None for value in quantiles):
                raise ValueError("Condemnation quantiles must be all present or all absent")
            return self
        q10, q50, q90 = quantiles
        if not q10 <= q50 <= q90:
            raise ValueError("Condemnation quantiles must be ordered")
        return self


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    status: Literal["processing", "completed", "failed"]
    request: AnalysisRequest
    result: AnalysisResult | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
