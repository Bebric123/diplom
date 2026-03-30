"""Pydantic-схемы публичного ингеста (/track, /logs/upload) — без FastAPI-приложения."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_MAX_CONTEXT_META_JSON = 65536
_MAX_LOG_CONTENT_CHARS = 2 * 1024 * 1024


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., max_length=64)
    action: str = Field(..., max_length=512)
    timestamp: str = Field(..., max_length=80)
    context: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _limit_payload_size(self):
        for name in ("context", "meta"):
            raw = json.dumps(getattr(self, name), ensure_ascii=False)
            if len(raw) > _MAX_CONTEXT_META_JSON:
                raise ValueError(f"{name} payload too large")
        return self


class LogFileCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: str = Field(..., max_length=64)
    filename: str = Field(..., max_length=512)
    content: str = Field(..., max_length=_MAX_LOG_CONTENT_CHARS)
    lines_sent: int = Field(..., ge=0, le=10_000_000)
    total_lines: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    server_name: Optional[str] = Field(default=None, max_length=256)
    service_name: Optional[str] = Field(default=None, max_length=256)
    environment: Optional[str] = Field(default="production", max_length=64)
    error_group_id: Optional[str] = Field(default=None, max_length=64)


class LogFileResponse(BaseModel):
    id: str
    filename: str
    lines_sent: int
    total_lines: Optional[int]
    created_at: str
    server_name: Optional[str]
    service_name: Optional[str]
