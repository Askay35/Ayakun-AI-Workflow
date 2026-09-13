"""Safe runtime settings editable from admin.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("description", sa.String(300), server_default="", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        """
        INSERT INTO runtime_settings (key, value, description, updated_at) VALUES
          ('simple_llm_model', '"deepseek-v4-flash"'::jsonb, 'Модель для быстрого режима', now()),
          ('complex_llm_model', '"deepseek-v4-pro"'::jsonb, 'Модель для точного режима', now()),
          ('web_search_provider', '"serper"'::jsonb, 'Провайдер веб-поиска', now()),
          ('llm_max_output_tokens', '8192'::jsonb, 'Технический максимум ответа модели', now())
        """
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
