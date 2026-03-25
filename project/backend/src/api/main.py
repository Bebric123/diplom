import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

app = FastAPI()
logger = logging.getLogger("collector")
settings = get_settings()
logger.info("REDIS_URL from settings: %s", settings.redis_url)


def get_platform_id(db: Session, platform_name: str) -> uuid.UUID:
    platform = db.query(Platform).filter(Platform.name == platform_name).first()
    if not platform:
        platform = Platform(name=platform_name)
        db.add(platform)
        db.flush()
    return platform.id


class EventCreate(BaseModel):
    project_id: str
    action: str
    timestamp: str
    context: Dict[str, Any]
    meta: Dict[str, Any]


@app.post("/track")
async def track_event(event_data: EventCreate, db: Session = Depends(get_db)):
    try:
        project_uuid = uuid.UUID(event_data.project_id)
        event = Event(
            project_id=project_uuid,
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
    project_id: str
    filename: str
    content: str
    lines_sent: int
    total_lines: Optional[int] = None
    server_name: Optional[str] = None
    service_name: Optional[str] = None
    environment: Optional[str] = "production"
    error_group_id: Optional[str] = None


class LogFileResponse(BaseModel):
    id: str
    filename: str
    lines_sent: int
    total_lines: Optional[int]
    created_at: str
    server_name: Optional[str]
    service_name: Optional[str]


@app.post("/logs/upload")
async def upload_log(log_data: LogFileCreate, db: Session = Depends(get_db)):
    try:
        project = db.query(Project).filter(Project.id == uuid.UUID(log_data.project_id)).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        log_file = LogFile(
            project_id=uuid.UUID(log_data.project_id),
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
    except Exception as e:
        db.rollback()
        logger.exception("Error uploading log file: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


async def process_log_sync(log_file: LogFile, db: Session):
    import hashlib

    from src.core.models import ErrorGroup, Platform
    from src.services.notifier import send_telegram_message_async

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

    error_text = "\n".join(errors[:5])
    group_hash = hashlib.sha256(f"{log_file.filename}{error_text}".encode()).hexdigest()

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

    await send_telegram_message_async(
        event={
            "title": f"Ошибки в логе: {log_file.filename}",
            "severity": "средняя",
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
    )

    logger.info("Log %s processed synchronously, notification sent", log_file.id)


@app.get("/logs/{log_id}")
async def get_log(log_id: str, db: Session = Depends(get_db)):
    try:
        log_uuid = uuid.UUID(log_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid log id") from e

    log_file = db.query(LogFile).filter(LogFile.id == log_uuid).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log not found")

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
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid project id") from e

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
