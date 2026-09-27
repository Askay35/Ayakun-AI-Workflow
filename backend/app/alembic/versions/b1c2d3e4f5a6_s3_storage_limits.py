"""Новые лимиты хранилища тарифов после переезда файлов на S3.

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans SET limits = limits || jsonb_build_object(
            'max_files', CASE code WHEN 'starter' THEN 200 WHEN 'pro' THEN 500 WHEN 'max' THEN 1000 END,
            'max_storage_mb', CASE code WHEN 'starter' THEN 2048 WHEN 'pro' THEN 4096 WHEN 'max' THEN 10240 END
        )
        WHERE code IN ('starter', 'pro', 'max')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans SET limits = limits || jsonb_build_object(
            'max_files', CASE code WHEN 'starter' THEN 50 WHEN 'pro' THEN 100 WHEN 'max' THEN 500 END,
            'max_storage_mb', CASE code WHEN 'starter' THEN 500 WHEN 'pro' THEN 1024 WHEN 'max' THEN 5120 END
        )
        WHERE code IN ('starter', 'pro', 'max')
        """
    )
