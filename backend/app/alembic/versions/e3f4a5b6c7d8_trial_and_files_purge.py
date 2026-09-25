"""Пробный период 7 дней и удаление файлов после окончания подписки.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS files_purge_at TIMESTAMPTZ")
    op.execute("UPDATE plans SET limits = limits || jsonb_build_object('period_days', 7) WHERE code = 'free'")
    # Уже закончившиеся подписки: три дня на продление отсчитываются от выкладки, файлы не удаляем сразу.
    op.execute(
        "UPDATE user_subscriptions SET files_purge_at = now() + interval '3 days' "
        "WHERE expires_at <= now() AND files_purge_at IS NULL"
    )
    # Пользователи без подписки получают пробный период с момента выкладки.
    op.execute(
        """
        INSERT INTO user_subscriptions (user_id, plan_id, status, started_at, expires_at, created_at, updated_at)
        SELECT u.id, p.id, 'active', now(), now() + interval '7 days', now(), now()
        FROM users u
        CROSS JOIN (SELECT id FROM plans WHERE code = 'free' LIMIT 1) p
        WHERE NOT EXISTS (SELECT 1 FROM user_subscriptions s WHERE s.user_id = u.id)
        ON CONFLICT (user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("UPDATE plans SET limits = limits || jsonb_build_object('period_days', 0) WHERE code = 'free'")
    op.execute("ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS files_purge_at")
