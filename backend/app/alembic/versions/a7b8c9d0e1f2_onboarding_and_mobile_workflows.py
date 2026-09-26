"""Опрос после регистрации и мобильные (линейные) цепочки.

Revision ID: a7b8c9d0e1f2
Revises: e3f4a5b6c7d8
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_answers JSONB")
    # Опрос показываем только новым пользователям.
    op.execute("UPDATE users SET onboarded_at = now() WHERE onboarded_at IS NULL")
    op.execute("ALTER TABLE workflows ADD COLUMN IF NOT EXISTS mobile BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE workflows DROP COLUMN IF EXISTS mobile")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarding_answers")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarded_at")
