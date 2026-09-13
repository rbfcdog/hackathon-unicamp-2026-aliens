import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.analysis import AgreementRange, EvidenceInput
from app.schemas.documents import DocumentPath, DocumentReference


class NewCaseData(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"]
    claim_amount: float = Field(gt=0, le=1_000_000_000)

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.strip().upper()


class ProcessDataReference(BaseModel):
    workbook_path: DocumentPath
    process_number: str = Field(min_length=1, max_length=64)

    @field_validator("workbook_path")
    @classmethod
    def validate_workbook_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.lower().endswith((".xlsx", ".xlsm")):
            raise ValueError("workbook_path must reference an XLSX or XLSM file")
        return normalized


class ProcessDataRecord(BaseModel):
    workbook_path: DocumentPath
    process_number: str
    state: str = Field(min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"]
    claim_amount: float = Field(gt=0)
    evidence: EvidenceInput
    source_rows: dict[str, int]
    excluded_post_outcome_columns: list[str]


class JudgeReviewRequest(BaseModel):
    case_number: str = Field(min_length=1, max_length=64)
    question: str = Field(
        default="Analise os pedidos, as provas e as defesas e proponha uma decisão fundamentada.",
        min_length=10,
        max_length=12_000,
    )
    documents: list[DocumentReference] = Field(min_length=1, max_length=100)
    process_data_reference: ProcessDataReference | None = None
    new_case_data: NewCaseData | None = None

    @model_validator(mode="after")
    def validate_input_source(self) -> "JudgeReviewRequest":
        paths = [document.path for document in self.documents]
        if len(set(paths)) != len(paths):
            raise ValueError("documents must not contain duplicate paths")
        if self.process_data_reference is not None and self.new_case_data is not None:
            raise ValueError("Provide at most one of process_data_reference or new_case_data")
        if self.process_data_reference is None:
            return self
        case_digits = "".join(character for character in self.case_number if character.isdigit())
        reference_digits = "".join(
            character
            for character in self.process_data_reference.process_number
            if character.isdigit()
        )
        if not case_digits or case_digits != reference_digits:
            raise ValueError("process_data_reference.process_number must match case_number")
        return self


class JudgeCitation(BaseModel):
    document_path: DocumentPath
    locator: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=1_000)


class JudgeFinding(BaseModel):
    issue: str = Field(min_length=1, max_length=500)
    conclusion: str = Field(min_length=1, max_length=1_000)
    reasoning: str = Field(min_length=1, max_length=4_000)
    citations: list[JudgeCitation] = Field(default_factory=list, max_length=20)


class JudgeDecision(BaseModel):
    disposition: Literal[
        "grant_claim",
        "deny_claim",
        "partial_grant",
        "insufficient_evidence",
    ]
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=20, max_length=6_000)
    findings: list[JudgeFinding] = Field(min_length=1, max_length=20)
    missing_evidence: list[str] = Field(default_factory=list, max_length=50)


class JudgeMLInputs(BaseModel):
    uf: str = Field(min_length=2, max_length=2)
    sub_subject: Literal["fraud", "generic"]
    claim_amount: float = Field(gt=0)
    claim_amount_usage: Literal["severity_only"]
    input_source: Literal[
        "workbook_row",
        "submitted_documents",
        "workbook_row_and_submitted_documents",
    ]
    evidence_document_paths: dict[str, list[DocumentPath]]
    evidence: EvidenceInput


class JudgeMLAnalysis(BaseModel):
    inputs: JudgeMLInputs
    loss_probability: float = Field(ge=0, le=1)
    expected_condemnation: float = Field(ge=0)
    condemnation_q10: float = Field(ge=0)
    condemnation_q50: float = Field(ge=0)
    condemnation_q90: float = Field(ge=0)
    model_disagreement: float = Field(ge=0, le=1)
    component_probabilities: dict[str, float]
    ensemble_weights: dict[str, float]
    requires_model_review: bool
    model_version: str
    limitations: list[str]


class JudgeStrategy(BaseModel):
    recommendation: Literal["agreement", "defense", "human_review"]
    risk_band: Literal["low", "medium", "high"]
    expected_defense_cost: float = Field(ge=0)
    evaluated_agreement_cost: float | None
    agreement_cheaper: bool | None
    agreement_range: AgreementRange | None
    next_action: Literal["propose_agreement", "prepare_defense", "human_review"]
    human_review_reason: str | None
    if_agreement_rejected: Literal["counterproposal"] | None


class JudgeReviewResponse(JudgeDecision):
    case_number: str
    consulted_documents: list[DocumentPath]
    unreadable_documents: list[DocumentPath]
    model: str
    trace_id: uuid.UUID
    langsmith_project: str
    tracing_enabled: bool
    ml_analysis: JudgeMLAnalysis | None
    ml_tool_errors: list[str]
    model_card_consulted: bool

    strategy: JudgeStrategy | None
    document_node_reads: dict[str, list[DocumentPath]]
    process_data: ProcessDataRecord | None


class DocumentCatalogItem(BaseModel):
    path: DocumentPath
    kind: Literal["pdf", "spreadsheet", "csv"]
    size_bytes: int = Field(ge=0)


class DocumentCatalogResponse(BaseModel):
    document_root: str
    documents: list[DocumentCatalogItem]
