import json
import logging
import uuid
from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.api.auth import reports_token_guard, require_project_api_key
from src.services.stats_service import aggregate_metrics, build_excel_report, resolve_time_range
from src.web.onboarding import router as onboarding_router
from src.core.config import get_settings
from src.core.database import get_db
from src.core.models import (
    Event,
    EventContext,
    EventError,
    EventUrl,
    LogFile,
    Platform,
    Project,
)

logger = logging.getLogger("collector")
settings = get_settings()
logger.info("REDIS_URL from settings: %s", settings.redis_url)

_MAX_CONTEXT_META_JSON = 65536
_MAX_LOG_CONTENT_CHARS = 2 * 1024 * 1024

app = FastAPI(title="Error Monitor Collector")

app.include_router(onboarding_router)


@app.get("/", include_in_schema=False)
def root_landing():
    return HTMLResponse(
        "<html><body style='font-family:system-ui;max-width:32rem;margin:2rem auto'>"
        "<h1>Error Monitor</h1>"
        "<p><a href=\"/register\">Регистрация проекта</a> — получить <code>project_id</code>, API-ключ и привязать Telegram.</p>"
        "<p><a href=\"/docs/sdk\">Инструкции по SDK</a> (Python, Node, PHP, HTTP, логи) · "
        "<a href=\"/docs\">OpenAPI (Swagger)</a> · <a href=\"/health\">health</a></p>"
        "</body></html>"
    )


@app.get("/health")
def health():
    return {"status": "ok"}


if settings.trusted_hosts_list():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts_list(),
    )

_cors = settings.cors_origins_list()
if _cors:
    if _cors == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_cors,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
        )


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.hsts_max_age and settings.hsts_max_age > 0:
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains"
        )
    return response


def get_platform_id(db: Session, platform_name: str) -> uuid.UUID:
    platform = db.query(Platform).filter(Platform.name == platform_name).first()
    if not platform:
        platform = Platform(name=platform_name)
        db.add(platform)
        db.flush()
    return platform.id


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


@app.post("/track")
async def track_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-Api-Key")] = None,
):
    try:
        project_uuid = uuid.UUID(event_data.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid project_id") from e

    api_key_row = require_project_api_key(db, project_uuid, authorization, x_api_key)

    try:
        event = Event(
            project_id=project_uuid,
            api_key_id=api_key_row.id if api_key_row else None,
            action=event_data.action,
            timestamp=event_data.timestamp,
            metadata_=event_data.meta,
        )
        db.add(event)
        db.flush()

        if "platform" in event_data.context:
            ctx = EventContext(
                event_id=event.id,
                platform_id=get_platform_id(db, event_data.context["platform"]),
                language=event_data.context.get("language"),
                os_family=event_data.context.get("os_family"),
                browser_family=event_data.context.get("browser_family"),
                browser_version=event_data.context.get("browser_version"),
            )
            db.add(ctx)

        if "page_url" in event_data.meta:
            url = EventUrl(
                event_id=event.id,
                page_url=event_data.meta.get("page_url"),
                page_path=event_data.meta.get("page_path"),
                domain=event_data.meta.get("domain"),
            )
            db.add(url)

        if "error_message" in event_data.meta:
            err = EventError(
                event_id=event.id,
                error_message=event_data.meta.get("error_message"),
                error_stack=event_data.meta.get("error_stack"),
                error_line=event_data.meta.get("error_line"),
                error_column=event_data.meta.get("error_column"),
                error_file=event_data.meta.get("error_file"),
            )
            db.add(err)

        db.commit()

        from src.workers.celery_app import celery_app

        celery_app.send_task("src.workers.tasks.process_event", args=[str(event.id)])

        return {"id": event.id}

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        db.rollback()
        logger.exception("Ошибка при обработке события")
        raise HTTPException(status_code=500, detail="Internal server error") from None


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


@app.post("/logs/upload")
async def upload_log(
    log_data: LogFileCreate,
    db: Session = Depends(get_db),
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-Api-Key")] = None,
):
    try:
        project_uuid = uuid.UUID(log_data.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid project_id") from e

    require_project_api_key(db, project_uuid, authorization, x_api_key)

    try:
        project = db.query(Project).filter(Project.id == project_uuid).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        log_file = LogFile(
            project_id=project_uuid,
            filename=log_data.filename,
            content=log_data.content,
            lines_sent=log_data.lines_sent,
            total_lines=log_data.total_lines,
            server_name=log_data.server_name,
            service_name=log_data.service_name,
            environment=log_data.environment,
            error_group_id=uuid.UUID(log_data.error_group_id) if log_data.error_group_id else None,
            file_size=len(log_data.content.encode("utf-8")),
            file_path=f"/logs/{log_data.project_id}/{log_data.filename}",
        )

        db.add(log_file)
        db.commit()
        db.refresh(log_file)

        try:
            from src.workers.tasks import process_log_file

            process_log_file.delay(str(log_file.id))
            logger.info("Log %s sent to Celery", log_file.id)
        except Exception as celery_error:
            logger.warning("Celery not available: %s, processing synchronously", celery_error)
            await process_log_sync(log_file, db)

        return {"id": str(log_file.id), "message": "Log file received successfully"}

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Error uploading log file")
        raise HTTPException(status_code=500, detail="Internal server error") from None


async def process_log_sync(log_file: LogFile, db: Session):
    import hashlib

    from src.core.models import ErrorGroup, Platform
    from src.services.notifier import (
        get_project_telegram_chat_id,
        send_telegram_message_async,
        should_send_notification,
        update_error_group_alert_anchor,
    )

    def _compact_text(s: str, max_len: int = 8000) -> str:
        if not s:
            return ""
        return " ".join(str(s).split())[:max_len]

    content = log_file.content
    lines = content.split("\n")

    errors = []
    warnings = []
    for line in lines:
        line_lower = line.lower()
        if "error" in line_lower or "exception" in line_lower or "critical" in line_lower:
            errors.append(line)
        elif "warn" in line_lower or "warning" in line_lower:
            warnings.append(line)

    if not errors:
        logger.info("No errors found in log %s", log_file.id)
        return

    error_text = _compact_text("\n".join(errors[:5]).replace("\n", " "))
    group_hash = hashlib.sha256(
        f"{log_file.filename}|{error_text}".encode()
    ).hexdigest()

    error_group = (
        db.query(ErrorGroup)
        .filter(
            ErrorGroup.project_id == log_file.project_id,
            ErrorGroup.group_hash == group_hash,
        )
        .first()
    )

    if not error_group:
        platform_name = log_file.service_name or "unknown"
        platform = db.query(Platform).filter(Platform.name == platform_name).first()
        if not platform:
            platform = Platform(name=platform_name)
            db.add(platform)
            db.flush()

        error_group = ErrorGroup(
            project_id=log_file.project_id,
            group_hash=group_hash,
            title=f"Log errors in {log_file.filename}",
            platform_id=platform.id,
            occurrence_count=len(errors),
            affected_users_count=1,
        )
        db.add(error_group)
        db.flush()
        logger.info("Created new error group: %s", error_group.id)
    else:
        error_group.occurrence_count += len(errors)
        db.flush()
        logger.info("Updated error group: %s", error_group.id)

    log_file.error_group_id = error_group.id
    db.commit()

    error_preview = "\n".join(errors[:3])
    severity_log = "средняя"

    if should_send_notification(db, error_group.id, severity_log, None):
        tg_chat = get_project_telegram_chat_id(db, log_file.project_id)
        if not tg_chat:
            logger.warning(
                "Project %s: нет telegram_chat_id — синхронный алерт по логу пропущен",
                log_file.project_id,
            )
        else:
            try:
                mid = await send_telegram_message_async(
                    event={
                        "title": f"Ошибки в логе: {log_file.filename}",
                        "severity": severity_log,
                        "criticality": "требует внимания",
                        "recommendation": f"Найдено {len(errors)} ошибок и {len(warnings)} предупреждений",
                        "page_url": f"/logs/{log_file.id}",
                        "user_id": "system",
                        "action": "log_analysis",
                        "context": {
                            "platform": "backend",
                            "language": "unknown",
                            "os_family": log_file.server_name or "unknown",
                            "browser_family": "server",
                        },
                        "meta": {
                            "filename": log_file.filename,
                            "errors_count": len(errors),
                            "warnings_count": len(warnings),
                            "lines_sent": log_file.lines_sent,
                            "total_lines": log_file.total_lines,
                            "environment": log_file.environment,
                            "server": log_file.server_name,
                            "service": log_file.service_name,
                            "first_errors": error_preview,
                            "log_id": str(log_file.id),
                        },
                    },
                    error_group_id=error_group.id,
                    telegram_chat_id=tg_chat,
                )
                if mid:
                    update_error_group_alert_anchor(db, error_group.id, severity_log)
                    db.commit()
                    logger.info("Log %s processed synchronously, notification sent", log_file.id)
            except Exception:
                db.rollback()
                raise
    else:
        logger.info(
            "Log %s sync path: telegram throttled for group %s",
            log_file.id,
            error_group.id,
        )


@app.get("/logs/{log_id}")
async def get_log(
    log_id: str,
    db: Session = Depends(get_db),
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-Api-Key")] = None,
):
    try:
        log_uuid = uuid.UUID(log_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid log id") from e

    log_file = db.query(LogFile).filter(LogFile.id == log_uuid).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log not found")

    require_project_api_key(db, log_file.project_id, authorization, x_api_key)

    return LogFileResponse(
        id=str(log_file.id),
        filename=log_file.filename,
        lines_sent=log_file.lines_sent,
        total_lines=log_file.total_lines,
        created_at=log_file.created_at.isoformat(),
        server_name=log_file.server_name,
        service_name=log_file.service_name,
    )


@app.get("/projects/{project_id}/logs")
async def list_project_logs(
    project_id: str,
    db: Session = Depends(get_db),
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-Api-Key")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid project id") from e

    require_project_api_key(db, proj_uuid, authorization, x_api_key)

    logs = (
        db.query(LogFile)
        .filter(LogFile.project_id == proj_uuid)
        .order_by(LogFile.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        LogFileResponse(
            id=str(log.id),
            filename=log.filename,
            lines_sent=log.lines_sent,
            total_lines=log.total_lines,
            created_at=log.created_at.isoformat(),
            server_name=log.server_name,
            service_name=log.service_name,
        )
        for log in logs
    ]


@app.get("/stats/summary")
def stats_summary(
    db: Session = Depends(get_db),
    _: None = Depends(reports_token_guard),
    date_from: Annotated[Optional[str], Query(alias="from")] = None,
    date_to: Annotated[Optional[str], Query(alias="to")] = None,
    project_id: Annotated[Optional[str], Query()] = None,
    days: Annotated[int, Query(ge=1, le=366)] = 7,
):
    start, end = resolve_time_range(date_from, date_to, default_days=days)
    pid = None
    if project_id:
        try:
            pid = uuid.UUID(project_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid project_id") from e
    return aggregate_metrics(db, start, end, pid)


@app.get("/reports/weekly.xlsx")
def report_weekly_xlsx(
    db: Session = Depends(get_db),
    _: None = Depends(reports_token_guard),
    date_from: Annotated[Optional[str], Query(alias="from")] = None,
    date_to: Annotated[Optional[str], Query(alias="to")] = None,
    project_id: Annotated[Optional[str], Query()] = None,
    days: Annotated[int, Query(ge=1, le=366)] = 7,
):
    start, end = resolve_time_range(date_from, date_to, default_days=days)
    pid = None
    if project_id:
        try:
            pid = uuid.UUID(project_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid project_id") from e
    blob = build_excel_report(db, start, end, pid)
    fname = f"report_{start.date()}_{end.date()}.xlsx"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
