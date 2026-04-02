import hashlib
import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from src.core.config import get_settings
from src.core.database import SessionLocal
from src.core.models import (
    CriticalityLevel,
    ErrorGroup,
    Event,
    EventContext,
    LogFile,
    Platform,
    Project,
    SeverityLevel,
)
from src.services.classifier import analyze_error
from src.services.notifier import (
    advisory_lock_notify_group,
    advisory_unlock_notify_group,
    build_log_alert_event_dict,
    create_error_task,
    get_project_telegram_chat_id,
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


def _compact_text(s: str, max_len: int = 8000) -> str:
    """Стабильный fingerprint для group_hash: схлопываем пробелы."""
    if not s:
        return ""
    return " ".join(str(s).split())[:max_len]


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
        "незначительно": "низкая",
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
        stmt = (
            select(Event)
            .options(
                joinedload(Event.context).joinedload(EventContext.platform),
                joinedload(Event.url),
                joinedload(Event.error),
            )
            .where(Event.id == uuid.UUID(event_id))
            .limit(1)
        )
        event = db.execute(stmt).unique().scalars().first()

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

        result = analyze_error(payload)

        severity_str = normalize_severity(result.get("severity", "средняя"))
        criticality_str = normalize_criticality(result.get("criticality", "требует внимания"))
        analysis_block = {
            "severity": severity_str,
            "criticality": criticality_str,
            "recommendation": result.get("recommendation", ""),
        }

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
        stack = _compact_text(stack)

        error_type = "unknown"
        if event.error and event.error.error_message:
            error_type = _compact_text(event.error.error_message.split("\n")[0][:500])
        elif event.metadata_:
            error_type = _compact_text(str(event.metadata_.get("error_message", "unknown"))[:500])

        group_hash = hashlib.sha256(
            f"{error_type}|{stack}|{page_url}".encode()
        ).hexdigest()

        error_group = db.scalars(
            select(ErrorGroup).where(
                ErrorGroup.project_id == event.project_id,
                ErrorGroup.group_hash == group_hash,
            )
        ).first()

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

            advisory_lock_notify_group(db, error_group.id)
            try:
                if not should_send_notification(db, error_group.id, severity_str, status_code):
                    logger.info("Notification throttled for group %s", error_group.id)
                else:
                    tg_chat = get_project_telegram_chat_id(db, event.project_id)
                    if not tg_chat:
                        logger.warning(
                            "Project %s: нет telegram_chat_id — алерт не отправлен",
                            event.project_id,
                        )
                    else:
                        error_task = create_error_task(
                            db=db,
                            event_id=event.id,
                            error_group_id=error_group.id,
                            project_id=event.project_id,
                        )
                        db.commit()

                        proj_row = db.get(Project, event.project_id)
                        project_name = proj_row.name if proj_row else "—"
                        created_iso = (
                            event.created_at.isoformat()
                            if event.created_at
                            else datetime.now(timezone.utc).isoformat()
                        )

                        message_id = send_telegram_message_sync(
                            event={
                                "title": title,
                                "severity": severity_str,
                                "criticality": criticality_str,
                                "recommendation": recommendation,
                                "page_url": page_url,
                                "group_id": str(error_group.id),
                                "group_occurrence_count": error_group.occurrence_count,
                                "user_id": str((event.metadata_ or {}).get("user_id", "anonymous")),
                                "action": event.action,
                                "context": context_data,
                                "meta": event.metadata_ or {},
                                "project_name": project_name,
                                "event_id": str(event.id),
                                "event_created_at": created_iso,
                                "group_id": str(error_group.id),
                                "analysis": analysis_block,
                            },
                            error_group_id=error_group.id,
                            task_id=error_task.id,
                            telegram_chat_id=tg_chat,
                        )

                        if message_id:
                            update_task_notification(
                                db=db,
                                task_id=error_task.id,
                                telegram_message_id=message_id,
                                telegram_chat_id=tg_chat,
                                severity=severity_str,
                            )
                            db.commit()
                            logger.info("Notification sent for group %s", error_group.id)
                        else:
                            logger.warning(
                                "Telegram не вернул message_id для группы %s (задача %s создана)",
                                error_group.id,
                                error_task.id,
                            )
            finally:
                advisory_unlock_notify_group(db, error_group.id)

        except Exception as e:
            logger.error("Failed to process notification: %s", e)

        logger.info("Event %s processed successfully, linked to group %s", event_id, error_group.id)

    except Exception as exc:
        try:
            db.rollback()
        except Exception as rb_err:
            logger.warning(
                "Rollback failed for event %s (connection may be stale): %s",
                event_id,
                rb_err,
            )
            try:
                db.invalidate()
            except Exception:
                pass
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

            severity_log = "средняя"

            advisory_lock_notify_group(db, error_group.id)
            try:
                if not should_send_notification(db, error_group.id, severity_log, None):
                    logger.info("Log telegram throttled for group %s", error_group.id)
                else:
                    tg_chat = get_project_telegram_chat_id(db, log_file.project_id)
                    if not tg_chat:
                        logger.warning(
                            "Project %s: нет telegram_chat_id — алерт по логу не отправлен",
                            log_file.project_id,
                        )
                    else:
                        payload = build_log_alert_event_dict(log_file, errors, warnings, log_id)
                        payload["group_occurrence_count"] = error_group.occurrence_count
                        log_ai = analyze_error(payload)
                        payload["analysis"] = {
                            "severity": normalize_severity(log_ai.get("severity", "средняя")),
                            "criticality": normalize_criticality(
                                log_ai.get("criticality", "требует внимания")
                            ),
                            "recommendation": log_ai.get("recommendation", ""),
                        }
                        meta = dict(payload.get("meta") or {})
                        ev = Event(
                            project_id=log_file.project_id,
                            action="log_analysis",
                            metadata_=meta,
                            error_group_id=error_group.id,
                        )
                        db.add(ev)
                        db.flush()
                        err_task = create_error_task(
                            db, ev.id, error_group.id, log_file.project_id
                        )
                        db.commit()

                        proj_log = db.get(Project, log_file.project_id)
                        payload["project_name"] = proj_log.name if proj_log else "—"
                        payload["event_id"] = str(ev.id)
                        payload["event_created_at"] = (
                            ev.created_at.isoformat()
                            if ev.created_at
                            else datetime.now(timezone.utc).isoformat()
                        )
                        payload["group_id"] = str(error_group.id)

                        message_id = send_telegram_message_sync(
                            payload,
                            error_group_id=error_group.id,
                            task_id=err_task.id,
                            telegram_chat_id=tg_chat,
                        )
                        if message_id:
                            update_task_notification(
                                db=db,
                                task_id=err_task.id,
                                telegram_message_id=message_id,
                                telegram_chat_id=tg_chat,
                                severity=severity_log,
                            )
                            db.commit()
                            logger.info("Telegram notification sent for log %s", log_id)
                        else:
                            logger.warning(
                                "Telegram не вернул message_id для лога %s (группа %s)",
                                log_id,
                                error_group.id,
                            )
            finally:
                advisory_unlock_notify_group(db, error_group.id)
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


@shared_task
def purge_old_monitoring_data():
    """Удаляет события и загруженные логи старше data_retention_days; затем группы без событий и логов."""
    s = get_settings()
    if not s.data_retention_enabled:
        logger.info("purge_old_monitoring_data: disabled")
        return {"ok": True, "skipped": True}

    days = max(30, min(int(s.data_retention_days), 365 * 5))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db = SessionLocal()
    try:
        n_logs = db.query(LogFile).filter(LogFile.created_at < cutoff).delete(
            synchronize_session=False
        )
        n_events = db.query(Event).filter(Event.created_at < cutoff).delete(
            synchronize_session=False
        )
        res = db.execute(
            text(
                """
                DELETE FROM error_groups eg
                WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.error_group_id = eg.id)
                  AND NOT EXISTS (SELECT 1 FROM log_files lf WHERE lf.error_group_id = eg.id)
                """
            )
        )
        n_groups = res.rowcount or 0
        db.commit()
        logger.info(
            "purge_old_monitoring_data: deleted logs=%s events=%s orphan_groups=%s (older than %s days)",
            n_logs,
            n_events,
            n_groups,
            days,
        )
        return {
            "ok": True,
            "days": days,
            "deleted_logs": n_logs,
            "deleted_events": n_events,
            "deleted_orphan_groups": n_groups,
        }
    except Exception:
        db.rollback()
        logger.exception("purge_old_monitoring_data failed")
        raise
    finally:
        db.close()


@shared_task
def send_weekly_stats_report():
    """Еженедельный отчёт: метрики + Excel в Telegram."""
    from src.services.stats_service import (
        aggregate_metrics,
        build_excel_report,
        default_range_days,
        send_excel_to_telegram,
    )

    s = get_settings()
    if not s.weekly_report_enabled:
        logger.info("Weekly report disabled via settings")
        return

    start, end = default_range_days(7)
    db = SessionLocal()
    try:
        metrics = aggregate_metrics(db, start, end, None)
        blob = build_excel_report(db, start, end, None)
    finally:
        db.close()

    cap = (
        f"📑 Еженедельный отчёт {start.date()} — {end.date()}\n"
        f"Событий с ошибкой: {metrics['events_with_errors']}\n"
        f"Задач: создано {metrics['tasks_created']}, решено {metrics['tasks_resolved']}"
    )
    fname = f"weekly_{start.date()}_{end.date()}.xlsx"
    try:
        send_excel_to_telegram(blob, cap, fname)
        logger.info("Weekly stats report sent to Telegram")
    except Exception as e:
        logger.error("Weekly report Telegram send failed: %s", e, exc_info=True)
        raise
