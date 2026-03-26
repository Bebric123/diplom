"""Проверка API-ключей для публичного collector API (ingest / чтение логов)."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.models import ApiKey


def hash_api_key(raw: str) -> str:
    s = get_settings()
    material = (s.api_key_pepper + raw).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def extract_api_key(
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> Optional[str]:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None
    return None


def require_project_api_key(
    db: Session,
    project_id: uuid.UUID,
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> Optional[ApiKey]:
    """Если в настройках включена проверка — требует валидный ключ для проекта."""
    s = get_settings()
    if not s.collector_require_api_key:
        return None
    raw = extract_api_key(authorization, x_api_key)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing API key")
    digest = hash_api_key(raw)
    row = (
        db.query(ApiKey)
        .filter(
            ApiKey.project_id == project_id,
            ApiKey.hashed_key == digest,
            ApiKey.is_revoked.is_(False),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")
    now = datetime.now(timezone.utc)
    if row.expires_at is not None:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            raise HTTPException(status_code=401, detail="API key expired")
    return row


def reports_token_guard(
    authorization: Annotated[Optional[str], Header()] = None,
    x_reports_token: Annotated[Optional[str], Header(alias="X-Reports-Token")] = None,
) -> None:
    """Если задан REPORTS_API_TOKEN — проверить Bearer или X-Reports-Token."""
    s = get_settings()
    if not s.reports_api_token:
        return
    got = extract_api_key(authorization, x_reports_token)
    if got != s.reports_api_token:
        raise HTTPException(status_code=401, detail="Invalid or missing reports token")
