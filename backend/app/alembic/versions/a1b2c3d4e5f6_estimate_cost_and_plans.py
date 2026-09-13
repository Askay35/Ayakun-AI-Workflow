"""Estimate workflow run cost and update billing plan economics.

Revision ID: a1b2c3d4e5f6
Revises: 9b31a7c4e2f0
Create Date: 2026-09-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9b31a7c4e2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("estimated_run_cost", sa.Numeric(18, 6), server_default="0", nullable=False),
    )
    op.execute(
        """
        UPDATE plans SET
          name = 'Free',
          price = 0,
          limits = '{"included_tokens": 3000, "parallel_runs": 3}'::jsonb
        WHERE code = 'free'
        """
    )
    op.execute(
        """
        INSERT INTO plans (code, name, price, currency, limits)
        SELECT 'standard', 'Standard', 990, 'RUB',
               '{"included_tokens": 100000, "parallel_runs": 10}'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM plans WHERE code = 'standard')
        """
    )
    op.execute(
        """
        UPDATE plans SET
          name = 'Pro',
          price = 2490,
          limits = '{"included_tokens": 300000, "parallel_runs": 30}'::jsonb
        WHERE code = 'pro'
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code = 'standard'")
    op.execute(
        """
        UPDATE plans SET
          name = 'Free',
          price = 0,
          limits = '{"workflows": 3, "scheduled_workflows": 1, "parallel_runs": 1, "included_tokens": 1000}'::jsonb
        WHERE code = 'free'
        """
    )
    op.execute(
        """
        UPDATE plans SET
          name = 'Pro',
          price = 990,
          limits = '{"workflows": 50, "scheduled_workflows": 20, "parallel_runs": 5, "included_tokens": 50000}'::jsonb
        WHERE code = 'pro'
        """
    )
    op.drop_column("workflows", "estimated_run_cost")
