"""Charge LLM usage at peak DeepSeek rates (2x off-peak) for 50% margin.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.014,
          input_cache_miss_credits_per_1k = 0.44,
          output_credits_per_1k = 1.32,
          provider_costs = '{"input_cache_hit_usd_per_million": 0.007, "input_cache_miss_usd_per_million": 0.22, "output_usd_per_million": 0.66, "peak_input_cache_hit_usd_per_million": 0.014, "peak_input_cache_miss_usd_per_million": 0.44, "peak_output_usd_per_million": 1.32, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
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
          provider_costs = '{"input_cache_hit_usd_per_million": 0.022, "input_cache_miss_usd_per_million": 0.66, "output_usd_per_million": 1.98, "peak_input_cache_hit_usd_per_million": 0.044, "peak_input_cache_miss_usd_per_million": 1.32, "peak_output_usd_per_million": 3.96, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-pro'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE pricing_rates SET
          input_cache_hit_credits_per_1k = 0.007,
          input_cache_miss_credits_per_1k = 0.22,
          output_credits_per_1k = 0.66,
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
          updated_at = now()
        WHERE provider = 'deepseek' AND model = 'deepseek-v4-pro'
        """
    )
