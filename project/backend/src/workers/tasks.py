import hashlib
import logging
import traceback
import uuid
from datetime import datetime

from celery import shared_task
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from src.core.database import SessionLocal
from src.core.models import (
    CriticalityLevel,
    ErrorGroup,
    Event,
    EventContext,
    LogFile,
    Platform,
    SeverityLevel,
)
from src.services.classifier import analyze_error_with_gigachat
from src.services.notifier import (
    TELEGRAM_CHAT_ID,
    create_error_task,
    send_telegram_message_sync,
    should_send_notification,
    update_task_notification,
)

logger = logging.getLogger("tasks")

SEVERITY_MAP: dict[str, uuid.UUID] = {}
CRITICALITY_MAP: dict[str, uuid.UUID] = {}


def load_reference_data() -> None:
    global SEVERITY_MAP, CRITICALITY_MAP
    with SessionLocal() as db:
        severities = db.execute(select(SeverityLevel)).scalars().all()
        criticalities = db.execute(select(CriticalityLevel)).scalars().all()
        SEVERITY_MAP = {s.name: s.id for s in severities}
        CRITICALITY_MAP = {c.name: c.id for c in criticalities}


load_reference_data()


def get_or_create_platform(db: Session, name: str) -> uuid.UUID:
    platform = db.query(Platform).filter(Platform.name == name).first()
    if not platform:
        platform = Platform(name=name)
        db.add(platform)
        db.flush()
        logger.info("Created new platform: %s", name)
    return platform.id


def normalize_severity(severity_str: str) -> str:
    severity = severity_str.lower().strip()
    severity_map = {
        "низкая": "низкая",
        "низкий": "низкая",
        "low": "низкая",
        "средняя": "средняя",
        "средний": "средняя",
        "medium": "средняя",
        "высокая": "высокая",
        "высокий": "высокая",
        "high": "высокая",
        "критическая": "критическая",
        "критичный": "критическая",
        "critical": "критическая",
    }
    return severity_map.get(severity, "средняя")


def normalize_criticality(criticality_str: str) -> str:
    criticality = criticality_str.lower().strip()
    criticality_map = {
        "не требует внимания": "не требует внимания",
        "не требует": "не требует внимания",
        "ignore": "не требует внимания",
        "требует внимания": "требует внимания",
        "требует": "требует внимания",
        "attention": "требует внимания",
        "критично": "критично",
        "критическая": "критично",
        "critical": "критично",
    }
    return criticality_map.get(criticality, "требует внимания")


@shared_task(bind=True, max_retries=3)
def process_event(self, event_id: str):
    db = SessionLocal()
    try:
        event = (
            db.query(Event)
            .options(
                joinedload(Event.context).joinedload(EventContext.platform),
                joinedload(Event.url),
                joinedload(Event.error),
            )
            .filter(Event.id == uuid.UUID(event_id))
            .first()
        )

        if not event:
            raise ValueError(f"Event {event_id} not found")

        page_url = "N/A"
        if event.url and event.url.page_url:
            page_url = event.url.page_url
        elif event.metadata_:
            page_url = event.metadata_.get("page_url", "N/A")

        error_message = "Unknown error"
        if event.error and event.error.error_message:
            error_message = event.error.error_message
        elif event.metadata_:
            error_message = event.metadata_.get("error_message", "Unknown error")

        context_data = {
            "platform": "unknown",
            "language": "javascript",
            "os_family": "unknown",
            "browser_family": "unknown",
        }

        if event.context:
            platform_name = "unknown"
            if event.context.platform:
                platform_name = event.context.platform.name
            elif event.context.platform_id:
                platform = db.get(Platform, event.context.platform_id)
                if platform:
                    platform_name = platform.name

            context_data = {
                "platform": platform_name,
                "language": event.context.language or "javascript",
                "os_family": event.context.os_family or "unknown",
                "browser_family": event.context.browser_family or "unknown",
            }

        payload = {
            "project_id": str(event.project_id),
            "action": event.action,
            "page_url": page_url,
            "context": context_data,
            "meta": event.metadata_ or {},
        }

        result = analyze_error_with_gigachat(payload)

        severity_str = normalize_severity(result.get("severity", "средняя"))
        criticality_str = normalize_criticality(result.get("criticality", "требует внимания"))

        severity_id = SEVERITY_MAP.get(severity_str)
        criticality_id = CRITICALITY_MAP.get(criticality_str)

        if not severity_id:
            logger.warning("Unknown severity: %s, using default", severity_str)
            severity_id = SEVERITY_MAP.get("средняя")

        if not criticality_id:
            logger.warning("Unknown criticality: %s, using default", criticality_str)
            criticality_id = CRITICALITY_MAP.get("требует внимания")

        platform_name = context_data["platform"]
        platform_id = get_or_create_platform(db, platform_name)

        stack = ""
        if event.error and event.error.error_stack:
            stack = event.error.error_stack
        elif event.metadata_:
            stack = event.metadata_.get("stack_trace", "")

        error_type = "unknown"
        if event.error and event.error.error_message:
            error_type = event.error.error_message.split("\n")[0][:100]
        elif event.metadata_:
            error_type = event.metadata_.get("error_message", "unknown")

        group_hash = hashlib.sha256(f"{error_type}{stack}{page_url}".encode()).hexdigest()

        error_group = db.execute(
            select(ErrorGroup).where(
                ErrorGroup.project_id == event.project_id,
                ErrorGroup.group_hash == group_hash,
            )
        ).scalar_one_or_none()

        title = error_message[:100]
        recommendation = result.get("recommendation", "")

        if not error_group:
            error_group = ErrorGroup(
                project_id=event.project_id,
                group_hash=group_hash,
                title=title,
                platform_id=platform_id,
                severity_id=severity_id,
                criticality_id=criticality_id,
                recommendation=recommendation,
                occurrence_count=1,
                affected_users_count=1,
            )
            db.add(error_group)
            db.flush()
            logger.info("Created new error group %s for event %s", error_group.id, event_id)
        else:
            error_group.occurrence_count += 1
            error_group.severity_id = severity_id
            error_group.criticality_id = criticality_id
            error_group.recommendation = recommendation
            error_group.last_seen_at = func.now()
            logger.info(
                "Updated error group %s, occurrence count: %s",
                error_group.id,
                error_group.occurrence_count,
            )

        event.error_group_id = error_group.id
        event.is_classified = True

        db.commit()

        try:
            status_code = event.metadata_.get("status_code") if event.metadata_ else None

            if should_send_notification(db, error_group.id, severity_str, status_code):
                error_task = create_error_task(
                    db=db,
                    event_id=event.id,
                    error_group_id=error_group.id,
                    project_id=event.project_id,
                )
                db.commit()

                message_id = send_telegram_message_sync(
                    event={
                        "title": title,
                        "severity": severity_str,
                        "criticality": criticality_str,
                        "recommendation": recommendation,
                        "page_url": page_url,
                        "group_id": str(error_group.id),
                        "user_id": getattr(event, "user_id", "anonymous"),
                        "action": event.action,
                        "context": context_data,
                        "meta": event.metadata_ or {},
                    },
                    error_group_id=error_group.id,
                    task_id=error_task.id,
                )

                if message_id:
                    update_task_notification(
                        db=db,
                        task_id=error_task.id,
                        telegram_message_id=message_id,
                        telegram_chat_id=TELEGRAM_CHAT_ID,
                        severity=severity_str,
                    )
                    db.commit()

                logger.info("Notification sent for group %s", error_group.id)
            else:
                logger.info("Notification throttled for group %s", error_group.id)

        except Exception as e:
            logger.error("Failed to process notification: %s", e)

        logger.info("Event %s processed successfully, linked to group %s", event_id, error_group.id)

    except Exception as exc:
        db.rollback()
        logger.error("Error processing event %s: %s", event_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        logger.error("Failed to process event %s after retries: %s", event_id, exc)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def process_log_file(self, log_id: str):
    db = SessionLocal()
    try:
        log_file = db.query(LogFile).filter(LogFile.id == uuid.UUID(log_id)).first()
        if not log_file:
            raise ValueError(f"Log file {log_id} not found")

        logger.info("Processing log file %s: %s", log_id, log_file.filename)

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

        logger.info("Log analysis: %s errors, %s warnings", len(errors), len(warnings))

        if errors:
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
                    logger.info("Created new platform: %s", platform_name)

                error_group = ErrorGroup(
                    project_id=log_file.project_id,
                    group_hash=group_hash,
                    title=f"Log errors in {log_file.filename}",
                    platform_id=platform.id,
                    occurrence_count=len(errors),
                    affected_users_count=1,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                db.add(error_group)
                db.flush()
                logger.info("Created new error group for log: %s", error_group.id)
            else:
                error_group.occurrence_count += len(errors)
                error_group.last_seen_at = datetime.utcnow()
                db.flush()
                logger.info(
                    "Updated error group %s, occurrence count: %s",
                    error_group.id,
                    error_group.occurrence_count,
                )

            log_file.error_group_id = error_group.id
            db.commit()

            error_preview = "\n".join(errors[:3]) if errors else "No errors"

            send_telegram_message_sync(
                event={
                    "title": f"Ошибки в логе: {log_file.filename}",
                    "severity": "средняя",
                    "criticality": "требует внимания",
                    "recommendation": f"Найдено {len(errors)} ошибок и {len(warnings)} предупреждений",
                    "page_url": f"/logs/{log_id}",
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

            logger.info("Telegram notification sent for log %s", log_id)
        else:
            logger.info("No errors found in log %s", log_id)

        logger.info("Log file %s processed successfully", log_id)

    except Exception as exc:
        db.rollback()
        logger.error("Error processing log file %s: %s", log_id, exc)
        logger.error(traceback.format_exc())
        if self.request.retries < self.max_retries:
            logger.info("Retrying log %s, attempt %s", log_id, self.request.retries + 1)
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        logger.error("Failed to process log file %s after retries", log_id)
    finally:
        db.close()
