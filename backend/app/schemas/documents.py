import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

DocumentPath = Annotated[str, Field(min_length=1, max_length=512)]
DocumentKind = Literal["pdf", "csv"]
EvidenceDocumentType = Literal[
    "case_record",
    "contract",
    "bank_statement",
    "credit_proof",
    "dossier",
    "debt_evolution",
    "referenced_report",
    "other",
]


class DocumentReference(BaseModel):
    path: DocumentPath
    document_type: EvidenceDocumentType

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return value.strip()


class UploadedDocumentResponse(BaseModel):
    upload_id: uuid.UUID
    path: DocumentPath
    kind: DocumentKind
    document_type: EvidenceDocumentType
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
