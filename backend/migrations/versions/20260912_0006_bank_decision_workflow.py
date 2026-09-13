"""Add lawyer justification and bank review state.

Revision ID: 20260912_0006
Revises: 20260912_0005
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0006"
down_revision: str | None = "20260912_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "process_decisions",
        sa.Column("justification", sa.Text(), nullable=True),
    )
    op.add_column(
        "process_decisions",
        sa.Column(
            "bank_status",
            sa.String(length=24),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "process_decisions",
        sa.Column("bank_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_process_decisions_bank_status"),
        "process_decisions",
        ["bank_status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_process_decisions_bank_status"), table_name="process_decisions")
    op.drop_column("process_decisions", "bank_reviewed_at")
    op.drop_column("process_decisions", "bank_status")
    op.drop_column("process_decisions", "justification")
