"""Credit billing, reservations and configurable provider pricing.

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b4c5d6e7f8a9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

uuid_t = postgresql.UUID(as_uuid=True)
json_t = postgresql.JSONB()


def upgrade() -> None:
    op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'purchase'")
    op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'charge'")
    op.alter_column("wallets", "currency", server_default="CRD")
    op.execute("UPDATE wallets SET currency = 'CRD'")

    op.add_column("usage_records", sa.Column("request_id", sa.String(160)))
    op.add_column("usage_records", sa.Column("provider", sa.String(50)))
    op.add_column("usage_records", sa.Column("model", sa.String(120)))
    op.add_column("usage_records", sa.Column("input_cache_hit_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("usage_records", sa.Column("input_cache_miss_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("usage_records", sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("usage_records", sa.Column("provider_cost_usd", sa.Numeric(18, 9), server_default="0", nullable=False))
    op.create_index("ix_usage_records_request_id", "usage_records", ["request_id"])

    op.create_table(
        "billing_reservations",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_run_id", uuid_t, sa.ForeignKey("workflow_runs.id"), nullable=True),
        sa.Column("request_id", sa.String(160), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("charged", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("released", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("metadata", json_t, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_billing_reservations_user_id", "billing_reservations", ["user_id"])
    op.create_index("ix_billing_reservations_workflow_run_id", "billing_reservations", ["workflow_run_id"])

    op.create_table(
        "pricing_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("input_cache_hit_credits_per_1k", sa.Numeric(18, 9), server_default="0", nullable=False),
        sa.Column("input_cache_miss_credits_per_1k", sa.Numeric(18, 9), server_default="0", nullable=False),
        sa.Column("output_credits_per_1k", sa.Numeric(18, 9), server_default="0", nullable=False),
        sa.Column("search_credits", sa.Numeric(18, 9), server_default="0", nullable=False),
        sa.Column("provider_costs", json_t, server_default="{}", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model", name="uq_pricing_provider_model"),
    )

    op.create_table(
        "billing_audit",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(160), nullable=False),
        sa.Column("before", json_t, server_default="{}", nullable=False),
        sa.Column("after", json_t, server_default="{}", nullable=False),
        sa.Column("request_id", sa.String(160), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.execute("UPDATE plans SET code = 'starter' WHERE code = 'standard'")
    op.execute(
        """
        INSERT INTO plans (code, name, price, currency, limits) VALUES
          ('free', 'Free', 0, 'RUB', '{"included_credits": 100, "run_cap_credits": 100, "parallel_runs": 1}'::jsonb),
          ('starter', 'Starter', 990, 'RUB', '{"included_credits": 5000, "run_cap_credits": 1000, "parallel_runs": 3}'::jsonb),
          ('pro', 'Pro', 1990, 'RUB', '{"included_credits": 15000, "run_cap_credits": 3000, "parallel_runs": 10}'::jsonb),
          ('max', 'Max', 3990, 'RUB', '{"included_credits": 50000, "run_cap_credits": 10000, "parallel_runs": 30}'::jsonb)
        ON CONFLICT (code) DO UPDATE SET
          name = EXCLUDED.name,
          price = EXCLUDED.price,
          currency = EXCLUDED.currency,
          limits = EXCLUDED.limits
        """
    )

    op.execute(
        """
        INSERT INTO pricing_rates (
          provider, model, input_cache_hit_credits_per_1k,
          input_cache_miss_credits_per_1k, output_credits_per_1k,
          search_credits, provider_costs, active, updated_at
        ) VALUES
          ('deepseek', 'deepseek-v4-flash', 0.007, 0.22, 0.66, 0,
           '{"input_cache_hit_usd_per_million": 0.007, "input_cache_miss_usd_per_million": 0.22, "output_usd_per_million": 0.66, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
           true, now()),
          ('deepseek', 'deepseek-v4-pro', 0.022, 0.66, 1.98, 0,
           '{"input_cache_hit_usd_per_million": 0.022, "input_cache_miss_usd_per_million": 0.66, "output_usd_per_million": 1.98, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
           true, now()),
          ('serper', 'search', 0, 0, 0, 1,
           '{"usd_per_request": 0.001, "gross_margin": 0.5, "credit_sale_price_usd": 0.002}'::jsonb,
           true, now())
        """
    )


def downgrade() -> None:
    op.drop_table("billing_audit")
    op.drop_table("pricing_rates")
    op.drop_index("ix_billing_reservations_workflow_run_id", table_name="billing_reservations")
    op.drop_index("ix_billing_reservations_user_id", table_name="billing_reservations")
    op.drop_table("billing_reservations")
    op.drop_index("ix_usage_records_request_id", table_name="usage_records")
    for column in (
        "provider_cost_usd", "output_tokens", "input_cache_miss_tokens",
        "input_cache_hit_tokens", "model", "provider", "request_id",
    ):
        op.drop_column("usage_records", column)
