"""Месячные тарифы: подписка пользователя, сгорание токенов, лимиты хранилища.

Revision ID: c1d2e3f4a5b6
Revises: c8d9e0f1a2b3
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'expire'")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
          plan_id INTEGER NOT NULL REFERENCES plans(id),
          status VARCHAR(20) NOT NULL DEFAULT 'active',
          started_at TIMESTAMPTZ NOT NULL,
          expires_at TIMESTAMPTZ NOT NULL,
          reminded_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_subscriptions_status ON user_subscriptions (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_subscriptions_expires_at ON user_subscriptions (expires_at)")
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
    op.execute("DROP TABLE IF EXISTS user_subscriptions")
