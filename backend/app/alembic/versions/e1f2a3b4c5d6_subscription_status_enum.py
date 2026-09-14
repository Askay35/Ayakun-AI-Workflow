"""create subscription_status enum

Revision ID: e1f2a3b4c5d6
Revises: d70435f2b612
Create Date: 2026-09-14 22:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d70435f2b612"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscription_status = sa.Enum("active", "inactive", name="subscription_status")


def upgrade() -> None:
    subscription_status.create(op.get_bind(), checkfirst=True)
    op.execute(
        """
        ALTER TABLE subscriptions
        ALTER COLUMN status TYPE subscription_status
        USING status::subscription_status
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE subscriptions
        ALTER COLUMN status TYPE VARCHAR(30)
        USING status::text
        """
    )
    subscription_status.drop(op.get_bind(), checkfirst=True)
