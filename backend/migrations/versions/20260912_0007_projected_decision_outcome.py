"""Persist the projected outcome created when the bank proceeds.

Revision ID: 20260912_0007
Revises: 20260912_0006
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0007"
down_revision: str | None = "20260912_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "process_decisions",
        sa.Column("projected_outcome", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "process_decisions",
        sa.Column("projected_outcome_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_process_decisions_projected_outcome"),
        "process_decisions",
        ["projected_outcome"],
    )
    op.execute(
        """
        UPDATE process_decisions
        SET projected_outcome = CASE
            WHEN recommendation = 'defense'
                AND COALESCE((model_snapshot -> 'risk' ->> 'loss_probability')::numeric, 1) < 0.5
                THEN 'favorable'
            WHEN recommendation = 'agreement'
                AND amount IS NOT NULL
                AND amount <= COALESCE(
                    (model_snapshot -> 'risk' ->> 'expected_condemnation')::numeric,
                    0
                )
                THEN 'favorable'
            ELSE 'unfavorable'
        END,
        projected_outcome_reason = 'Projeção recalculada com o snapshot do modelo salvo na decisão.'
        WHERE bank_status = 'approved'
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_process_decisions_projected_outcome"),
        table_name="process_decisions",
    )
    op.drop_column("process_decisions", "projected_outcome_reason")
    op.drop_column("process_decisions", "projected_outcome")
