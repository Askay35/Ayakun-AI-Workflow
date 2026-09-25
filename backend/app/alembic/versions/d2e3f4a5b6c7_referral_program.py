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
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_referral_code') THEN
            ALTER TABLE users ADD CONSTRAINT uq_users_referral_code UNIQUE (referral_code);
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_referred_by_id') THEN
            ALTER TABLE users ADD CONSTRAINT fk_users_referred_by_id
              FOREIGN KEY (referred_by_id) REFERENCES users(id) ON DELETE SET NULL;
          END IF;
        END $$
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_referred_by_id ON users (referred_by_id)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_referred_by_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_referred_by_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_referral_code")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referred_by_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referral_code")
