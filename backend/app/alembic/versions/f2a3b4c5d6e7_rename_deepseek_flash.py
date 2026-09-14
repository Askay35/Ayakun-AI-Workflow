"""rename deepseek-v4-flash to deepseek-flash

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-14 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates
        SET model = 'deepseek-flash'
        WHERE provider = 'deepseek'
          AND model = 'deepseek-v4-flash'
          AND NOT EXISTS (
            SELECT 1 FROM pricing_rates other
            WHERE other.provider = 'deepseek' AND other.model = 'deepseek-flash'
          )
        """
    )
    op.execute(
        """
        DELETE FROM pricing_rates
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-flash'
        """
    )
    op.execute(
        """
        UPDATE runtime_settings
        SET value = '"deepseek-flash"'::jsonb
        WHERE key = 'simple_llm_model'
          AND value::text LIKE '%deepseek-v4-flash%'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates
        SET model = 'deepseek-v4-flash'
        WHERE provider = 'deepseek'
          AND model = 'deepseek-flash'
          AND NOT EXISTS (
            SELECT 1 FROM pricing_rates other
            WHERE other.provider = 'deepseek' AND other.model = 'deepseek-v4-flash'
          )
        """
    )
    op.execute(
        """
        UPDATE runtime_settings
        SET value = '"deepseek-v4-flash"'::jsonb
        WHERE key = 'simple_llm_model'
          AND value::text LIKE '%deepseek-flash%'
          AND value::text NOT LIKE '%deepseek-v4-flash%'
        """
    )
