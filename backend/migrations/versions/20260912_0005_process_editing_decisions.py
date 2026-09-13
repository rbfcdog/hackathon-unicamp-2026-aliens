"""Persist edited model inputs and submitted process decisions.

Revision ID: 20260912_0005
Revises: 20260912_0004
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0005"
down_revision: str | None = "20260912_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "legal_processes",
        sa.Column(
            "model_inputs_edited",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_table(
        "process_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column(
            "model_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["process_id"],
            ["legal_processes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_process_decisions_process_id"),
        "process_decisions",
        ["process_id"],
    )
    op.create_index(
        op.f("ix_process_decisions_recommendation"),
        "process_decisions",
        ["recommendation"],
    )
    op.create_index(
        op.f("ix_process_decisions_created_at"),
        "process_decisions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_process_decisions_created_at"), table_name="process_decisions")
    op.drop_index(op.f("ix_process_decisions_recommendation"), table_name="process_decisions")
    op.drop_index(op.f("ix_process_decisions_process_id"), table_name="process_decisions")
    op.drop_table("process_decisions")
    op.drop_column("legal_processes", "model_inputs_edited")
