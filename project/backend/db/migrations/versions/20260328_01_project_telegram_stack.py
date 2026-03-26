"""Проект: чат Telegram и стек для онбординга.

Revision ID: 20260328_01
Revises: 20260327_01
"""

from alembic import op

revision = "20260328_01"
down_revision = "20260327_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.projects
            ADD COLUMN IF NOT EXISTS telegram_chat_id varchar(64),
            ADD COLUMN IF NOT EXISTS tech_stack jsonb DEFAULT '[]'::jsonb;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.projects DROP COLUMN IF EXISTS tech_stack")
    op.execute("ALTER TABLE public.projects DROP COLUMN IF EXISTS telegram_chat_id")
