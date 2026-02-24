# backend/src/workers/tasks.py

from celery import shared_task
from sqlalchemy.orm import Session
from src.core.database import engine
from src.core.models import Event, ErrorGroup, SeverityLevel, CriticalityLevel
from src.services.classifier import analyze_error_with_gigachat  # ← ваша функция
from src.services.notifier import send_telegram_message
import hashlib

@shared_task(bind=True, max_retries=3)
def process_event(self, event_id: str):
    db = Session(engine)
    try:
        # 1. Загружаем событие
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # 2. Формируем данные для анализа
        event_data = {
            "project_id": str(event.project_id),
            "action": event.action,
            "page_url": event.metadata_.get("page_url", "N/A"),
            "timestamp": event.timestamp.isoformat(),
            "context": {},
            "metadata": event.metadata_
        }

        # Добавляем контекст из связанных таблиц (4НФ)
        if hasattr(event, 'context') and event.context:
            event_data["context"] = {
                "platform": event.context.platform.name if event.context.platform else "unknown",
                "language": event.context.language,
                "os_family": event.context.os_family,
                "browser_family": event.context.browser_family
            }

        # 3. Анализируем через GigaChat
        analysis = analyze_error_with_gigachat(event_data)

        # 4. Группировка ошибок
        error_msg = event.metadata_.get("error_message", "")
        stack = event.metadata_.get("error_stack", "")[:200]
        group_hash = hashlib.sha256(f"{error_msg}::{stack}".encode()).hexdigest()

        error_group = db.query(ErrorGroup).filter_by(
            project_id=event.project_id,
            group_hash=group_hash
        ).first()

        if not error_group:
            error_group = ErrorGroup(
                project_id=event.project_id,
                group_hash=group_hash,
                title=error_msg[:100] or "Unknown error",
                platform_id=event.context.platform_id if hasattr(event, 'context') else None
            )
            db.add(error_group)
            db.flush()

        # 5. Обновляем группу
        severity = db.query(SeverityLevel).filter(SeverityLevel.name == analysis["severity"]).first()
        criticality = db.query(CriticalityLevel).filter(CriticalityLevel.name == analysis["criticality"]).first()

        error_group.severity_id = severity.id if severity else None
        error_group.criticality_id = criticality.id if criticality else None
        error_group.recommendation = analysis["recommendation"]
        error_group.occurrence_count += 1

        # 6. Отправляем уведомление
        send_telegram_message(event, error_group, analysis)

        # 7. Помечаем как обработанное
        event.is_classified = True
        event.is_notified = True
        db.commit()

    except Exception as exc:
        db.rollback()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        else:
            print(f"Failed to process event {event_id}: {exc}")
    finally:
        db.close()