from celery import shared_task
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, create_engine, func  
from src.core.models import Event, ErrorGroup, SeverityLevel, CriticalityLevel, Platform, EventContext
from src.services.classifier import analyze_error_with_gigachat
from src.services.notifier import create_error_task, send_telegram_message_sync, update_task_notification, should_send_notification, TELEGRAM_CHAT_ID

import asyncio
import uuid
import logging
import hashlib

# Настройка логгера
logger = logging.getLogger("tasks")

# Настройка движка (замените на вашу строку подключения)
DATABASE_URL = "postgresql://postgres:postgres@db:5432/Monitoring"
engine = create_engine(DATABASE_URL)

# Глобальные маппинги (загружаются один раз при старте)
SEVERITY_MAP = {}
CRITICALITY_MAP = {}

def load_reference_data():
    """Загружает справочники severity/criticality в память."""
    global SEVERITY_MAP, CRITICALITY_MAP
    with Session(engine) as db:
        severities = db.execute(select(SeverityLevel)).scalars().all()
        criticalities = db.execute(select(CriticalityLevel)).scalars().all()
        SEVERITY_MAP = {s.name: s.id for s in severities}
        CRITICALITY_MAP = {c.name: c.id for c in criticalities}

# Загрузка при импорте
load_reference_data()

def get_or_create_platform(db: Session, name: str) -> uuid.UUID:
    platform = db.execute(select(Platform).where(Platform.name == name)).scalar_one_or_none()
    if not platform:
        platform = Platform(name=name)
        db.add(platform)
        db.flush()
    return platform.id

def normalize_severity(severity_str: str) -> str:
    """Нормализует строку severity от GigaChat"""
    # Приводим к нижнему регистру
    severity = severity_str.lower().strip()
    
    # Маппинг возможных вариантов
    severity_map = {
        'низкая': 'низкая',
        'низкий': 'низкая',
        'low': 'низкая',
        'средняя': 'средняя',
        'средний': 'средняя',
        'medium': 'средняя',
        'высокая': 'высокая',
        'высокий': 'высокая',
        'high': 'высокая',
        'критическая': 'критическая',
        'критичный': 'критическая',
        'critical': 'критическая'
    }
    
    return severity_map.get(severity, 'средняя')  # По умолчанию средняя

def normalize_criticality(criticality_str: str) -> str:
    """Нормализует строку criticality от GigaChat"""
    criticality = criticality_str.lower().strip()
    
    criticality_map = {
        'не требует внимания': 'не требует внимания',
        'не требует': 'не требует внимания',
        'ignore': 'не требует внимания',
        'требует внимания': 'требует внимания',
        'требует': 'требует внимания',
        'attention': 'требует внимания',
        'критично': 'критично',
        'критическая': 'критично',
        'critical': 'критично'
    }
    
    return criticality_map.get(criticality, 'требует внимания')

@shared_task(bind=True, max_retries=3)
def process_event(self, event_id: str):
    db = Session(engine)
    try:
        # 1. Получаем событие со всеми связанными данными
        event = db.query(Event)\
            .options(
                joinedload(Event.context).joinedload(EventContext.platform),
                joinedload(Event.url),
                joinedload(Event.error)
            )\
            .filter(Event.id == uuid.UUID(event_id))\
            .first()

        if not event:
            raise ValueError(f"Event {event_id} not found")

        # 2. Извлекаем page_url
        page_url = "N/A"
        if event.url and event.url.page_url:
            page_url = event.url.page_url
        elif event.metadata_:
            page_url = event.metadata_.get("page_url", "N/A")

        # 3. Извлекаем error_message
        error_message = "Unknown error"
        if event.error and event.error.error_message:
            error_message = event.error.error_message
        elif event.metadata_:
            error_message = event.metadata_.get("error_message", "Unknown error")

        # 4. Формируем контекст
        context_data = {
            "platform": "unknown",
            "language": "javascript",
            "os_family": "unknown",
            "browser_family": "unknown"
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
                "browser_family": event.context.browser_family or "unknown"
            }

        # 5. Формируем payload для GigaChat
        payload = {
            "project_id": str(event.project_id),
            "action": event.action,
            "page_url": page_url,
            "context": context_data,
            "meta": event.metadata_ or {}
        }

        # 6. Анализ через GigaChat
        result = analyze_error_with_gigachat(payload)

        # 7. Нормализация severity и criticality
        severity_str = normalize_severity(result.get("severity", "средняя"))
        criticality_str = normalize_criticality(result.get("criticality", "требует внимания"))

        severity_id = SEVERITY_MAP.get(severity_str)
        criticality_id = CRITICALITY_MAP.get(criticality_str)

        if not severity_id:
            logger.warning(f"Unknown severity: {severity_str}, using default")
            severity_id = SEVERITY_MAP.get("средняя")
            
        if not criticality_id:
            logger.warning(f"Unknown criticality: {criticality_str}, using default")
            criticality_id = CRITICALITY_MAP.get("требует внимания")

        # 8. Получаем platform_id
        platform_name = context_data["platform"]
        platform_id = get_or_create_platform(db, platform_name)

        # 9. Генерируем group_hash на основе данных события
        stack = ""
        if event.error and event.error.error_stack:
            stack = event.error.error_stack
        elif event.metadata_:
            stack = event.metadata_.get("stack_trace", "")
        
        # Создаём хеш для группы ошибок
        group_hash = hashlib.sha256(f"{stack}{page_url}".encode()).hexdigest()

        # 10. Ищем существующую группу ошибок
        error_group = db.execute(
            select(ErrorGroup).where(
                ErrorGroup.project_id == event.project_id,
                ErrorGroup.group_hash == group_hash
            )
        ).scalar_one_or_none()

        title = error_message[:100]
        recommendation = result.get("recommendation", "")

        if not error_group:
            # Создаём новую группу
            error_group = ErrorGroup(
                project_id=event.project_id,
                group_hash=group_hash,
                title=title,
                platform_id=platform_id,
                severity_id=severity_id,
                criticality_id=criticality_id,
                recommendation=recommendation,
                occurrence_count=1,
                affected_users_count=1
            )
            db.add(error_group)
            db.flush()  # Получаем ID группы
            
            logger.info(f"Created new error group {error_group.id} for event {event_id}")
        else:
            # Обновляем существующую группу
            error_group.occurrence_count += 1
            error_group.severity_id = severity_id
            error_group.criticality_id = criticality_id
            error_group.recommendation = recommendation
            error_group.last_seen_at = func.now()
            
            logger.info(f"Updated error group {error_group.id}, occurrence count: {error_group.occurrence_count}")

        # 11. Обновляем событие - добавляем ссылку на группу ошибок
        event.error_group_id = error_group.id
        event.is_classified = True
        
        db.commit()

        # 12. Отправка уведомления
        def run_async(coro):
            """Запускает корутину в новом event loop"""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        try:
            # Получаем status_code из meta если есть
            status_code = event.metadata_.get("status_code") if event.metadata_ else None
            
            # Проверяем, нужно ли отправлять уведомление
            if should_send_notification(db, error_group.id, severity_str, status_code):
                # Создаём задачу в error_tasks
                error_task = create_error_task(
                    db=db,
                    event_id=event.id,
                    error_group_id=error_group.id,
                    project_id=event.project_id
                )
                db.commit()
                
                # Отправляем уведомление
                message_id = send_telegram_message_sync(
                    event={
                        "title": title,
                        "severity": severity_str,
                        "criticality": criticality_str,
                        "recommendation": recommendation,
                        "page_url": page_url,
                        "group_id": str(error_group.id),
                        "user_id": getattr(event, 'user_id', 'anonymous'),
                        "action": event.action,
                        "context": context_data,
                        "meta": event.metadata_ or {}
                    },
                    error_group_id=error_group.id,
                    task_id=error_task.id
                )
                
                # Обновляем задачу с ID сообщения
                if message_id:
                    update_task_notification(
                        db=db,
                        task_id=error_task.id,
                        telegram_message_id=message_id,
                        telegram_chat_id=TELEGRAM_CHAT_ID,
                        severity=severity_str  # Передаём severity
                    )
                    db.commit()
                    
                logger.info(f"📨 Notification sent for group {error_group.id}")
            else:
                logger.info(f"⏱️ Notification throttled for group {error_group.id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to process notification: {e}")
                
        except Exception as e:
            logger.error(f"❌ Failed to process notification: {e}")

        logger.info(f"Event {event_id} processed successfully, linked to group {error_group.id}")

    except Exception as exc:
        db.rollback()
        logger.error(f"Error processing event {event_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        else:
            logger.error(f"Failed to process event {event_id} after retries: {exc}")
    finally:
        db.close()