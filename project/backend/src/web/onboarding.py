"""
Регистрация проекта: стек + Telegram chat id → project_id + API-ключ для SDK.
"""
from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.api.auth import hash_api_key
from src.core.database import get_db
from src.core.models import ApiKey, Project

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["onboarding"])

# Значения value в форме → сохраняются в project.tech_stack
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
    {"value": "mobile_react_native", "label": "React Native"},
    {"value": "mobile_flutter", "label": "Flutter"},
    {"value": "dotnet", "label": ".NET"},
    {"value": "java_spring", "label": "Java / Spring"},
    {"value": "go", "label": "Go"},
    {"value": "php", "label": "PHP"},
    {"value": "other", "label": "Другое"},
]

_ALLOWED = {c["value"] for c in STACK_CHOICES}
_CHAT_ID_RE = re.compile(r"^-?\d{6,}$")


class RegisterApiBody(BaseModel):
    project_name: str = Field(default="Новый проект", max_length=200)
    telegram_chat_id: str = Field(..., min_length=1, max_length=32)
    stack: List[str] = Field(default_factory=list)

    @field_validator("telegram_chat_id")
    @classmethod
    def chat_ok(cls, v: str) -> str:
        s = v.strip()
        if not _CHAT_ID_RE.match(s):
            raise ValueError("Некорректный Telegram chat id (только цифры, для групп с минусом в начале)")
        return s

    @field_validator("stack", mode="before")
    @classmethod
    def stack_filter(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v in _ALLOWED else []
        return [x for x in v if x in _ALLOWED][:24]


def _create_project_with_key(
    db: Session,
    project_name: str,
    telegram_chat_id: str,
    stack: List[str],
) -> tuple[Project, str]:
    name = (project_name or "Новый проект").strip()[:200] or "Новый проект"
    project = Project(
        name=name,
        description=None,
        telegram_chat_id=telegram_chat_id.strip(),
        tech_stack=stack or [],
    )
    db.add(project)
    db.flush()

    raw_key = secrets.token_urlsafe(32)
    row = ApiKey(
        project_id=project.id,
        name="ingest",
        hashed_key=hash_api_key(raw_key),
        scope=["ingest"],
        is_revoked=False,
    )
    db.add(row)
    db.commit()
    db.refresh(project)
    return project, raw_key


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "stack_choices": STACK_CHOICES},
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    project_name: str = Form("Новый проект"),
    telegram_chat_id: str = Form(...),
    stack: List[str] = Form(default=[]),
):
    tid = (telegram_chat_id or "").strip()
    if not _CHAT_ID_RE.match(tid):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "stack_choices": STACK_CHOICES,
                "error": "Некорректный Telegram chat id. Нужны только цифры (для групп — с минусом в начале, например -100…).",
            },
            status_code=400,
        )
    stack_clean = [s for s in stack if s in _ALLOWED][:24]

    project, api_key_plain = _create_project_with_key(db, project_name, tid, stack_clean)
    return templates.TemplateResponse(
        "register_done.html",
        {
            "request": request,
            "project_id": str(project.id),
            "api_key": api_key_plain,
            "project_name": project.name,
            "telegram_chat_id": tid,
            "stack": stack_clean,
        },
    )


@router.post("/api/register", response_model=None)
def register_api(body: RegisterApiBody, db: Session = Depends(get_db)):
    """JSON-регистрация (для скриптов). Ключ показывается один раз."""
    project, api_key_plain = _create_project_with_key(
        db,
        body.project_name,
        body.telegram_chat_id,
        body.stack,
    )
    return {
        "project_id": str(project.id),
        "api_key": api_key_plain,
        "project_name": project.name,
        "telegram_chat_id": project.telegram_chat_id,
        "tech_stack": project.tech_stack or [],
    }
