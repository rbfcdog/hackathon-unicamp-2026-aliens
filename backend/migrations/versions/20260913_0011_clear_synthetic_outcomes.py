# Migration clears only the demonstrative outcomes created by the prior negotiation migration.
"""Clear historical synthetic agreement outcomes.

Revision ID: 20260913_0011
Revises: 20260913_0010
Create Date: 2026-09-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260913_0011"
down_revision: str | None = "20260913_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE process_decisions
        SET outcome = 'pending',
            actual_cost = NULL,
            outcome_recorded_at = NULL,
            negotiation_status = 'pending',
            negotiation_amount = NULL,
            negotiation_updated_at = NULL
        WHERE recommendation = 'agreement'
          AND bank_status = 'approved'
          AND outcome = 'settled'
          AND (actual_cost = amount OR (actual_cost IS NULL AND amount IS NULL))
          AND outcome_recorded_at = COALESCE(bank_reviewed_at, created_at)
          AND negotiation_status = 'accepted'
          AND (negotiation_amount = amount OR (negotiation_amount IS NULL AND amount IS NULL))
          AND negotiation_updated_at = COALESCE(bank_reviewed_at, created_at)
        """
    )


def downgrade() -> None:
    # A downgrade must not recreate fictitious results.
    pass
