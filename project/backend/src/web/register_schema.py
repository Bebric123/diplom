"""Схема JSON-регистрации и константы формы (без Form-зависимостей FastAPI)."""
from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel, Field, field_validator

STACK_CHOICES = [
    {"value": "python_fastapi", "label": "Python / FastAPI"},
    {"value": "python_flask", "label": "Python / Flask"},
    {"value": "python_django", "label": "Python / Django"},
    {"value": "python_other", "label": "Python (другое)"},
    {"value": "nodejs_express", "label": "Node.js / Express"},
    {"value": "nodejs_fastify", "label": "Node.js / Fastify"},
    {"value": "nodejs_nest", "label": "Node.js / Nest"},
    {"value": "react", "label": "React"},
    {"value": "vue", "label": "Vue"},
    {"value": "angular", "label": "Angular"},
    {"value": "php", "label": "PHP"},
    {"value": "other", "label": "Другое"},
]

_ALLOWED = {c["value"] for c in STACK_CHOICES}
_CHAT_ID_RE = re.compile(r"^-?\d{6,}$")


def normalize_telegram_chat_id(raw: str) -> str:
    return (raw or "").strip().replace(" ", "")


class RegisterApiBody(BaseModel):
    project_name: str = Field(default="Новый проект", max_length=200)
    telegram_chat_id: str = Field(..., min_length=1, max_length=32)
    stack: List[str] = Field(default_factory=list)

    @field_validator("telegram_chat_id")
    @classmethod
    def chat_ok(cls, v: str) -> str:
        s = normalize_telegram_chat_id(v)
        if not _CHAT_ID_RE.match(s):
            raise ValueError(
                "Некорректный Telegram chat id (только цифры, для групп с минусом в начале)"
            )
        return s

    @field_validator("stack", mode="before")
    @classmethod
    def stack_filter(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v in _ALLOWED else []
        return [x for x in v if x in _ALLOWED][:24]
