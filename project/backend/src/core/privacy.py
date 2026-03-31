"""Идентификаторы и PII на стороне коллектора.

- API-ключи ingest: только SHA256(pepper + ключ), см. src.api.auth.hash_api_key.
- В событиях /track поле meta приходит от клиента как есть; сервер не хранит отдельную таблицу
  профилей пользователей. Чтобы не светить email/login в БД, клиент может слать уже обрезанный
  идентификатор или хеш — ниже хелпер для единообразия.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def hash_user_identifier(value: str, *, secret: Optional[str] = None) -> str:
    """
    Стабильный односторонний идентификатор (hex). Если задан secret — HMAC-SHA256,
    иначе SHA256 от нормализованной строки (без секрета слабее к перебору).
    """
    raw = (value or "").strip().lower().encode("utf-8")
    if secret:
        return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hashlib.sha256(raw).hexdigest()
