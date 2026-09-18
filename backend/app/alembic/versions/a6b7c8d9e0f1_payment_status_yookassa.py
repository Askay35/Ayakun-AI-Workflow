"""Align payment_status enum with YooKassa values.

Revision ID: a6b7c8d9e0f1
Revises: f4a5b6c7d8e9
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'payment_status' AND e.enumlabel = 'cancelled'
          ) AND NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'payment_status' AND e.enumlabel = 'canceled'
          ) THEN
            ALTER TYPE payment_status RENAME VALUE 'cancelled' TO 'canceled';
          END IF;

          IF NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'payment_status' AND e.enumlabel = 'waiting_for_capture'
          ) THEN
            ALTER TYPE payment_status ADD VALUE 'waiting_for_capture';
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'payment_status' AND e.enumlabel = 'canceled'
          ) AND NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'payment_status' AND e.enumlabel = 'cancelled'
          ) THEN
            ALTER TYPE payment_status RENAME VALUE 'canceled' TO 'cancelled';
          END IF;
        END
        $$;
        """
    )
