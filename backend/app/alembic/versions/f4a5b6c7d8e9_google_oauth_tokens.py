"""Store Google refresh tokens for Gmail.

Revision ID: f4a5b6c7d8e9
Revises: e0f1a2b3c4d5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("google_sub", sa.String(length=320), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "google_sub", name="uq_gmail_user_google_sub"),
    )
    op.create_index("ix_google_oauth_tokens_user_id", "google_oauth_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_google_oauth_tokens_user_id", table_name="google_oauth_tokens")
    op.drop_table("google_oauth_tokens")
