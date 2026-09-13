# Migration preserves agreement negotiation state without fabricating case outcomes.
"""Track agreement negotiation state without inventing results.

Revision ID: 20260913_0010
Revises: 20260913_0009
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0010"
down_revision: str | None = "20260913_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.add_column(
        "process_decisions",
        sa.Column(
            "negotiation_status",
            sa.String(length=24),
            server_default="not_applicable",
            nullable=False,
        ),
    )
    op.add_column(
        "process_decisions",
        sa.Column("negotiation_amount", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "process_decisions",
        sa.Column("negotiation_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_process_decisions_negotiation_status"),
        "process_decisions",
        ["negotiation_status"],
    )
    op.execute(
        """
        UPDATE process_decisions
        SET negotiation_status = 'pending',
            negotiation_amount = NULL,
            negotiation_updated_at = NULL
        WHERE recommendation = 'agreement'
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_process_decisions_negotiation_status"),
        table_name="process_decisions",
    )
    op.drop_column("process_decisions", "negotiation_updated_at")
    op.drop_column("process_decisions", "negotiation_amount")
    op.drop_column("process_decisions", "negotiation_status")

