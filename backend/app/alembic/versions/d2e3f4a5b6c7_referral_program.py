"""Реферальная программа: код приглашения, кто пригласил, бонусы в ledger.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ledger_kind ADD VALUE IF NOT EXISTS 'referral'")
    op.add_column("users", sa.Column("referral_code", sa.String(16), nullable=True))
    op.add_column("users", sa.Column("referred_by_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.create_foreign_key(
        "fk_users_referred_by_id", "users", "users", ["referred_by_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_referred_by_id", "users", ["referred_by_id"])


def downgrade() -> None:
    op.drop_index("ix_users_referred_by_id", table_name="users")
    op.drop_constraint("fk_users_referred_by_id", "users", type_="foreignkey")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referred_by_id")
    op.drop_column("users", "referral_code")
