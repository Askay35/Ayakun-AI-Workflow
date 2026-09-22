"""Настройки медиа: провайдер распознавания и цены в токенах.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
"""

from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO runtime_settings (key, value, description, updated_at) VALUES
          ('vision_provider', '"deepseek"'::jsonb, 'Провайдер распознавания изображений: deepseek или gigachat', now()),
          ('image_generation_credits', '50'::jsonb, 'Цена генерации изображения, токены', now()),
          ('image_recognition_credits_deepseek', '25'::jsonb, 'Цена распознавания через DeepSeek, токены', now()),
          ('image_recognition_credits_gigachat', '40'::jsonb, 'Цена распознавания через GigaChat, токены', now()),
          ('audio_minute_credits', '2.564103'::jsonb, 'Цена расшифровки аудио за минуту, токены', now())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM runtime_settings WHERE key IN (
          'vision_provider',
          'image_generation_credits',
          'image_recognition_credits_deepseek',
          'image_recognition_credits_gigachat',
          'audio_minute_credits'
        )
        """
    )
