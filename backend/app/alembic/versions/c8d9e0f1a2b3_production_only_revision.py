"""Ревизия, применённая на проде, файл которой не попал в репозиторий.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2

Пустая: восстанавливает цепочку, чтобы alembic мог продолжить с этой ревизии.
Следующие миграции написаны идемпотентно и не зависят от её содержимого.
"""

from typing import Sequence, Union

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
