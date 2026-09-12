import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.documents import canonical_process_number
from app.schemas.analysis import EvidenceInput


class LegalProcessCreate(BaseModel):
    case_number: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    state: str = Field(min_length=2, max_length=2)
    subject: str | None = Field(default=None, max_length=255)
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


class LegalProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    title: str
    location: str
    state: str
    subject: str
    sub_subject: str
    claim_amount: float
    evidence: EvidenceInput
    default_question: str
    is_draft: bool
    created_at: datetime
    updated_at: datetime
