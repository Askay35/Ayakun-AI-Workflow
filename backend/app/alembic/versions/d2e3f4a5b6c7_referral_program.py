"""Реферальная программа: код приглашения, кто пригласил, бонусы в ledger.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'referral'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(16)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by_id INTEGER")
    op.execute(
        """
        DO $$
        BEGIN
          -- Ревизия c8d9e0f1a2b3 на проде уже создала уникальный индекс и FK под другими именами.
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_referral_code')
             AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'users' AND indexname = 'ix_users_referral_code') THEN
            ALTER TABLE users ADD CONSTRAINT uq_users_referral_code UNIQUE (referral_code);
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname IN ('fk_users_referred_by_id', 'fk_users_referred_by')) THEN
            ALTER TABLE users ADD CONSTRAINT fk_users_referred_by_id
              FOREIGN KEY (referred_by_id) REFERENCES users(id) ON DELETE SET NULL;
          END IF;
        END $$
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_referred_by_id ON users (referred_by_id)")
    # Старые коды — hex в нижнем регистре; ссылки и проверка кода работают в верхнем.
    op.execute("UPDATE users SET referral_code = upper(referral_code) WHERE referral_code <> upper(referral_code)")
    # Бонусы, начисленные ревизией c8d9e0f1a2b3, переводим в kind=referral, чтобы их было видно на странице «Рефералы».
    op.execute(
        """
        UPDATE wallet_ledger l
        SET kind = 'referral',
            metadata = l.metadata || jsonb_build_object(
              'role', 'referrer',
              'referee_id', (l.metadata->>'referral_user_id')::int,
              'referee_name', u.name,
              'payment_id', l.reference
            )
        FROM users u
        WHERE l.kind = 'credit'
          AND l.idempotency_key LIKE 'referral-referrer:%'
          AND u.id = (l.metadata->>'referral_user_id')::int
        """
    )
    op.execute(
        """
        UPDATE wallet_ledger
        SET kind = 'referral',
            metadata = metadata || jsonb_build_object('role', 'referee', 'payment_id', reference)
        WHERE kind = 'credit' AND idempotency_key LIKE 'referral-buyer:%'
        """
    )
    op.execute(
        """
        UPDATE wallet_ledger l
        SET metadata = l.metadata || jsonb_build_object('plan_name', p.name)
        FROM payments pay JOIN plans p ON p.id = pay.plan_id
        WHERE l.kind = 'referral' AND pay.id::text = l.reference AND NOT (l.metadata ? 'plan_name')
        """
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_referred_by_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_referred_by_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_referral_code")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referred_by_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referral_code")
