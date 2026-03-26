"""Плейсхолдер: ревизия уже была записана в alembic_version в БД, файла не было в репо.

Revision ID: 69240d419bbb
Revises:
Create Date: 2026-03-26
"""

revision = "69240d419bbb"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # схема из init.sql; ревизия нужна только как якорь в alembic_version


def downgrade() -> None:
    pass
