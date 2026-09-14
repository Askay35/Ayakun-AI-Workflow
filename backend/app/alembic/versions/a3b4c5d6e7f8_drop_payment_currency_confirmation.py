"""drop payments.currency and confirmation_url

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-15 01:27:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("payments", "confirmation_url")
    op.drop_column("payments", "currency")


def downgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
    )
    op.add_column(
        "payments",
        sa.Column("confirmation_url", sa.Text(), nullable=True),
    )
    op.alter_column("payments", "currency", server_default=None)
