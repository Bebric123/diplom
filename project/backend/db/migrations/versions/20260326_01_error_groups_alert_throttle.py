"""Колонки троттлинга алертов для error_groups.

Revision ID: 20260326_01
Revises: 69240d419bbb
Create Date: 2026-03-26
"""

from alembic import op

revision = "20260326_01"
down_revision = "69240d419bbb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: безопасно и при старой БД без колонок, и если init.sql уже создал полную схему
    op.execute(
        """
        ALTER TABLE public.error_groups
            ADD COLUMN IF NOT EXISTS alert_last_sent_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS alert_last_severity text;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.error_groups DROP COLUMN IF EXISTS alert_last_severity")
    op.execute("ALTER TABLE public.error_groups DROP COLUMN IF EXISTS alert_last_sent_at")
