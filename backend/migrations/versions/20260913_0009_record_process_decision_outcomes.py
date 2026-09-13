"""Replace projected decision outcomes with recorded case results.

Revision ID: 20260913_0009
Revises: 20260913_0008
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0009"
down_revision: str | None = "20260913_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_process_decisions_projected_outcome", table_name="process_decisions")
    op.drop_column("process_decisions", "projected_outcome_reason")
    op.drop_column("process_decisions", "projected_outcome")
    op.add_column(
        "process_decisions",
        sa.Column(
            "outcome",
            sa.String(length=24),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "process_decisions",
        sa.Column("actual_cost", sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        "process_decisions",
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_process_decisions_outcome", "process_decisions", ["outcome"])


def downgrade() -> None:
    op.drop_index("ix_process_decisions_outcome", table_name="process_decisions")
    op.drop_column("process_decisions", "outcome_recorded_at")
    op.drop_column("process_decisions", "actual_cost")
    op.drop_column("process_decisions", "outcome")
    op.add_column(
        "process_decisions",
        sa.Column("projected_outcome", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "process_decisions",
        sa.Column("projected_outcome_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_process_decisions_projected_outcome",
        "process_decisions",
        ["projected_outcome"],
    )
