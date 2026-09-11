"""Use provider-cost rates for credit conversion.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.007,
          input_cache_miss_credits_per_1k = 0.22,
          output_credits_per_1k = 0.66,
          provider_costs = '{"input_cache_hit_usd_per_million": 0.007, "input_cache_miss_usd_per_million": 0.22, "output_usd_per_million": 0.66, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-flash'
        """
    )
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.022,
          input_cache_miss_credits_per_1k = 0.66,
          output_credits_per_1k = 1.98,
          provider_costs = '{"input_cache_hit_usd_per_million": 0.022, "input_cache_miss_usd_per_million": 0.66, "output_usd_per_million": 1.98, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-pro'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.014,
          input_cache_miss_credits_per_1k = 0.44,
          output_credits_per_1k = 1.32,
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-flash'
        """
    )
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.044,
          input_cache_miss_credits_per_1k = 1.32,
          output_credits_per_1k = 3.96,
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-pro'
        """
    )
