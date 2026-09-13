"""Ayakun MVP backend

Revision ID: 9b31a7c4e2f0
Revises: d2fd5c2ee128
"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b31a7c4e2f0"
down_revision: str | Sequence[str] | None = "d2fd5c2ee128"
branch_labels = None
depends_on = None

uuid_t = postgresql.UUID(as_uuid=True)
json_t = postgresql.JSONB()


def upgrade() -> None:
    op.alter_column("users", "name", type_=sa.String(120), existing_type=sa.String(30))
    op.alter_column("users", "email", type_=sa.String(320), existing_type=sa.String())
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))

    identity_provider = sa.Enum("email", "google", "telegram", name="identity_provider")
    workflow_status = sa.Enum("draft", "published", "archived", name="workflow_status")
    run_status = sa.Enum("queued", "running", "succeeded", "failed", "cancelled", name="run_status")
    node_run_status = sa.Enum("pending", "running", "succeeded", "failed", "cancelled", name="node_run_status")
    ledger_kind = sa.Enum("credit", "reserve", "settle", "release", "refund", name="ledger_kind")
    payment_status = sa.Enum("pending", "succeeded", "cancelled", name="payment_status")

    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", identity_provider, nullable=False),
        sa.Column("subject", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_provider_subject"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "workflows",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("draft_graph", json_t, nullable=False),
        sa.Column("published_version_id", uuid_t),
        sa.Column("schedule_cron", sa.String(100)),
        sa.Column("schedule_timezone", sa.String(64), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflows_owner_id", "workflows", ["owner_id"])
    op.create_index("ix_workflows_next_run_at", "workflows", ["next_run_at"])
    op.create_table(
        "workflow_versions",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("workflow_id", uuid_t, sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph_snapshot", json_t, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
    op.create_table(
        "workflow_runs",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("workflow_id", uuid_t, sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_version_id", uuid_t, sa.ForeignKey("workflow_versions.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("input", json_t, nullable=False),
        sa.Column("output", json_t),
        sa.Column("error", sa.Text()),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("workflow_id", "workflow_version_id", "owner_id"):
        op.create_index(f"ix_workflow_runs_{name}", "workflow_runs", [name])
    op.create_table(
        "node_runs",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("workflow_run_id", uuid_t, sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(120), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("status", node_run_status, nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input", json_t, nullable=False),
        sa.Column("output", json_t),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workflow_run_id", "node_id", name="uq_node_run_once"),
    )
    op.create_index("ix_node_runs_workflow_run_id", "node_runs", ["workflow_run_id"])

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TOK"),
        sa.Column("limits", json_t, nullable=False),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_table(
        "wallets",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("balance", sa.Numeric(18, 6), nullable=False),
        sa.Column("reserved", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "wallet_ledger",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", ledger_kind, nullable=False),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("reference", sa.String(160)),
        sa.Column("metadata", json_t, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
    op.create_table(
        "usage_records",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_run_id", uuid_t, sa.ForeignKey("workflow_runs.id")),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("details", json_t, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_usage_user_key"),
    )
    op.create_index("ix_usage_records_user_id", "usage_records", ["user_id"])
    op.create_table(
        "payments",
        sa.Column("id", uuid_t, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id")),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_payment_id", sa.String(100), unique=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("confirmation_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.execute(
        """
        INSERT INTO plans (code, name, price, currency, limits) VALUES
        ('free', 'Free', 0, 'RUB',
         '{"included_tokens": 3000, "parallel_runs": 3}'::jsonb),
        ('standard', 'Standard', 990, 'RUB',
         '{"included_tokens": 100000, "parallel_runs": 10}'::jsonb),
        ('pro', 'Pro', 2490, 'RUB',
         '{"included_tokens": 300000, "parallel_runs": 30}'::jsonb)
        """
    )


def downgrade() -> None:
    for table in (
        "payments", "usage_records", "wallet_ledger", "wallets", "subscriptions", "plans",
        "node_runs", "workflow_runs", "workflow_versions", "workflows", "refresh_tokens", "auth_identities",
    ):
        op.drop_table(table)
    op.drop_column("users", "is_active")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column("users", "email", type_=sa.String(), existing_type=sa.String(320))
    op.alter_column("users", "name", type_=sa.String(30), existing_type=sa.String(120))
    bind = op.get_bind()
    for enum_name in (
        "payment_status",
        "ledger_kind",
        "node_run_status",
        "run_status",
        "workflow_status",
        "identity_provider",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
