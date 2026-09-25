"""Месячные тарифы: подписка пользователя, сгорание токенов, лимиты хранилища.

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'expire'")
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])
    op.create_index("ix_user_subscriptions_expires_at", "user_subscriptions", ["expires_at"])
    op.execute(
        """
        UPDATE plans SET
          name = CASE code WHEN 'max' THEN 'Супер' ELSE name END,
          limits = limits
            || jsonb_build_object(
              'included_credits', CASE code WHEN 'free' THEN 100 ELSE COALESCE((limits->>'included_credits')::numeric, 0) END,
              'max_files', CASE code WHEN 'free' THEN 20 WHEN 'starter' THEN 50 WHEN 'pro' THEN 100 WHEN 'max' THEN 500 ELSE 20 END,
              'max_storage_mb', CASE code WHEN 'free' THEN 100 WHEN 'starter' THEN 500 WHEN 'pro' THEN 1024 WHEN 'max' THEN 5120 ELSE 100 END,
              'period_days', CASE code WHEN 'free' THEN 0 ELSE 30 END
            )
        """
    )


def downgrade() -> None:
    op.execute("UPDATE plans SET name = 'Макс' WHERE code = 'max'")
    op.execute("UPDATE plans SET limits = limits - 'max_files' - 'max_storage_mb' - 'period_days'")
    op.drop_index("ix_user_subscriptions_expires_at", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_status", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
