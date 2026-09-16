"""Add unique webhook token on workflows.

Revision ID: e0f1a2b3c4d5
Revises: d8e9f0a1b2c3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("webhook_token", sa.String(length=80), nullable=True))
    op.create_index("ix_workflows_webhook_token", "workflows", ["webhook_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_workflows_webhook_token", table_name="workflows")
    op.drop_column("workflows", "webhook_token")
