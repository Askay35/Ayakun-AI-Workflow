"""Set free plan included credits to 100.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
"""

from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET limits = jsonb_set(limits, '{included_credits}', '100'::jsonb, true)
        WHERE code = 'free'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET limits = jsonb_set(limits, '{included_credits}', '500'::jsonb, true)
        WHERE code = 'free'
        """
    )
