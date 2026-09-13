"""Remove location and subject from persisted legal processes.

Revision ID: 20260913_0008
Revises: 20260912_0007
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0008"
down_revision: str | None = "20260912_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("legal_processes", "location")
    op.drop_column("legal_processes", "subject")
    op.execute(
        """
        UPDATE process_decisions
        SET model_snapshot = model_snapshot - 'location' - 'subject'
        WHERE model_snapshot ?| ARRAY['location', 'subject']
        """
    )


def downgrade() -> None:
    op.add_column(
        "legal_processes",
        sa.Column("location", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "legal_processes",
        sa.Column("subject", sa.String(length=255), nullable=True),
    )
    op.execute("UPDATE legal_processes SET location = state, subject = 'Processo jurídico'")
    op.alter_column("legal_processes", "location", nullable=False)
    op.alter_column("legal_processes", "subject", nullable=False)
