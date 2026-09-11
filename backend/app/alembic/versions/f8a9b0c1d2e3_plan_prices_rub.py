"""Set plan prices to RUB.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE plans SET currency = 'RUB', price = 0 WHERE code = 'free'")
    op.execute("UPDATE plans SET currency = 'RUB', price = 990 WHERE code = 'starter'")
    op.execute("UPDATE plans SET currency = 'RUB', price = 1990 WHERE code = 'pro'")
    op.execute("UPDATE plans SET currency = 'RUB', price = 3990 WHERE code = 'max'")


def downgrade() -> None:
    op.execute("UPDATE plans SET currency = 'USD', price = 0 WHERE code = 'free'")
    op.execute("UPDATE plans SET currency = 'USD', price = 9 WHERE code = 'starter'")
    op.execute("UPDATE plans SET currency = 'USD', price = 19 WHERE code = 'pro'")
    op.execute("UPDATE plans SET currency = 'USD', price = 49 WHERE code = 'max'")
