"""Валидация тел без поднятия HTTP-сервера (импорт main подтягивает модели)."""
from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from src.api.schemas_ingest import EventCreate


def test_event_create_rejects_huge_meta():
    huge = {"k": "x" * 100_000}
    with pytest.raises(ValidationError):
        EventCreate(
            project_id=str(uuid.uuid4()),
            action="a",
            timestamp="2026-03-30T12:00:00Z",
            context={},
            meta=huge,
        )


def test_event_create_accepts_minimal():
    e = EventCreate(
        project_id=str(uuid.uuid4()),
        action="click",
        timestamp="2026-03-30T12:00:00Z",
        context={"platform": "web"},
        meta={"page_url": "https://a.test/"},
    )
    assert e.action == "click"


def test_event_create_context_meta_json_limit():
    ctx = {"platform": "p", "extra": "y" * 70_000}
    raw = json.dumps({"context": ctx, "meta": {}}, ensure_ascii=False)
    assert len(raw) > 65536
    with pytest.raises(ValidationError):
        EventCreate(
            project_id=str(uuid.uuid4()),
            action="a",
            timestamp="2026-03-30T12:00:00Z",
            context=ctx,
            meta={},
        )
