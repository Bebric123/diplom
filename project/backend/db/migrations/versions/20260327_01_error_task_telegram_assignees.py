"""Поля: кто взял задачу в работу и кто закрыл (Telegram).

Revision ID: 20260327_01
Revises: 20260326_01
"""

from alembic import op

revision = "20260327_01"
down_revision = "20260326_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.error_tasks
            ADD COLUMN IF NOT EXISTS acknowledged_by_telegram_user_id bigint,
            ADD COLUMN IF NOT EXISTS acknowledged_by_label varchar(255),
            ADD COLUMN IF NOT EXISTS resolved_by_telegram_user_id bigint,
            ADD COLUMN IF NOT EXISTS resolved_by_label varchar(255);
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.error_tasks DROP COLUMN IF EXISTS resolved_by_label"
    )
    op.execute(
        "ALTER TABLE public.error_tasks DROP COLUMN IF EXISTS resolved_by_telegram_user_id"
    )
    op.execute(
        "ALTER TABLE public.error_tasks DROP COLUMN IF EXISTS acknowledged_by_label"
    )
    op.execute(
        "ALTER TABLE public.error_tasks DROP COLUMN IF EXISTS acknowledged_by_telegram_user_id"
    )
