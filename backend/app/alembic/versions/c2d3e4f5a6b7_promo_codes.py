"""Промокоды: скидка на тариф при подключении, учёт использований.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

uuid_t = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("plan_ids", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_promo_codes_code"),
    )
    op.create_table(
        "promo_code_redemptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("promo_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", uuid_t, nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promo_code_id", "user_id", name="uq_promo_redemption_user"),
        sa.UniqueConstraint("payment_id", name="uq_promo_redemption_payment"),
    )
    op.create_index("ix_promo_code_redemptions_promo_code_id", "promo_code_redemptions", ["promo_code_id"])
    op.create_index("ix_promo_code_redemptions_user_id", "promo_code_redemptions", ["user_id"])
    op.add_column("payments", sa.Column("promo_code_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("discount_percent", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_payments_promo_code_id", "payments", "promo_codes", ["promo_code_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_promo_code_id", "payments", type_="foreignkey")
    op.drop_column("payments", "discount_percent")
    op.drop_column("payments", "promo_code_id")
    op.drop_index("ix_promo_code_redemptions_user_id", table_name="promo_code_redemptions")
    op.drop_index("ix_promo_code_redemptions_promo_code_id", table_name="promo_code_redemptions")
    op.drop_table("promo_code_redemptions")
    op.drop_table("promo_codes")
