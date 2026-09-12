"""Create persisted legal processes for the single-lawyer workspace.

Revision ID: 20260912_0003
Revises: 20260912_0002
Create Date: 2026-09-12
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0003"
down_revision: str | None = "20260912_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


legal_processes = sa.table(
    "legal_processes",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("case_number", sa.String()),
    sa.column("canonical_number", sa.String()),
    sa.column("title", sa.String()),
    sa.column("location", sa.String()),
    sa.column("state", sa.String()),
    sa.column("subject", sa.String()),
    sa.column("sub_subject", sa.String()),
    sa.column("claim_amount", sa.Numeric()),
    sa.column("evidence", postgresql.JSONB()),
    sa.column("default_question", sa.Text()),
)


def upgrade() -> None:
    op.create_table(
        "legal_processes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(length=64), nullable=False),
        sa.Column("canonical_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("sub_subject", sa.String(length=16), nullable=False),
        sa.Column("claim_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("default_question", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_number", name="uq_legal_processes_canonical_number"),
    )
    op.create_index(op.f("ix_legal_processes_case_number"), "legal_processes", ["case_number"])

    op.bulk_insert(
        legal_processes,
        [
            {
                "id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
                "case_number": "0801234-56.2024.8.10.0001",
                "canonical_number": "08012345620248100001",
                "title": "Caso 01 · São Luís",
                "location": "São Luís · MA",
                "state": "MA",
                "subject": "Relação bancária",
                "sub_subject": "generic",
                "claim_amount": 20000,
                "evidence": {
                    "contract": True,
                    "bank_statement": True,
                    "credit_proof": True,
                    "dossier": True,
                    "debt_evolution": True,
                    "referenced_report": True,
                },
                "default_question": (
                    "Analise a existência da contratação, do crédito e da dívida e apresente "
                    "uma decisão fundamentada."
                ),
            },
            {
                "id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
                "case_number": "0654321-09.2024.8.04.0001",
                "canonical_number": "06543210920248040001",
                "title": "Caso 02 · Amazonas",
                "location": "Amazonas · AM",
                "state": "AM",
                "subject": "Suspeita de fraude bancária",
                "sub_subject": "fraud",
                "claim_amount": 25000,
                "evidence": {
                    "contract": False,
                    "bank_statement": False,
                    "credit_proof": True,
                    "dossier": False,
                    "debt_evolution": True,
                    "referenced_report": True,
                },
                "default_question": (
                    "Compare as alegações com as provas de crédito e evolução da dívida e "
                    "indique contradições ou documentos ausentes."
                ),
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_legal_processes_case_number"), table_name="legal_processes")
    op.drop_table("legal_processes")
