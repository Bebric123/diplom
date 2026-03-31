"""Сопоставление Telegram-чата с проектом (по telegram_chat_id из регистрации)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.core.models import Project
from src.web.register_schema import normalize_telegram_chat_id


def project_for_telegram_chat(db: Session, chat_id: int) -> Optional[Project]:
    """Активный проект, у которого в БД сохранён этот chat id (как при /register)."""
    tid = normalize_telegram_chat_id(str(chat_id))
    if not tid:
        return None
    return (
        db.query(Project)
        .filter(
            Project.is_active.is_(True),
            Project.telegram_chat_id == tid,
        )
        .first()
    )


def is_group_like_chat(chat_type: Optional[str]) -> bool:
    return chat_type in ("group", "supergroup")
