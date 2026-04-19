"""
Регистрация проекта: стек + Telegram chat id → project_id + API-ключ для SDK.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.api.auth import hash_api_key
from src.core.database import get_db
from src.core.models import ApiKey, Project
from src.web.register_schema import (
    STACK_CHOICES,
    RegisterApiBody,
    _ALLOWED,
    _CHAT_ID_RE,
    normalize_telegram_chat_id,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["onboarding"])


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


@router.get("/docs/sdk", response_class=HTMLResponse)
def sdk_guide(request: Request):
    """Боковая панель с инструкциями: языки SDK, HTTP, логи, ошибки."""
    return templates.TemplateResponse("sdk_guide.html", {"request": request})


@router.get("/docs/telegram", response_class=HTMLResponse)
def telegram_guide(request: Request):
    """Как создать бота, добавить в чат, узнать chat id и связать с проектом."""
    return templates.TemplateResponse("telegram_guide.html", {"request": request})


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
    tid = normalize_telegram_chat_id(telegram_chat_id)
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
