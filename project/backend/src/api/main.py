from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.models import Event, EventContext, EventUrl, EventError, Platform
from src.core.database import get_db
from pydantic import BaseModel
import logging  
from typing import Optional, Dict, Any
from src.core.config import get_settings


app = FastAPI()
logger = logging.getLogger("collector")

settings = get_settings()
logger.info(f"✅ REDIS_URL from settings: {settings.redis_url}")

def get_platform_id(db: Session, platform_name: str) -> str:
    """Получает ID платформы по имени. Создаёт, если не существует."""
    platform = db.query(Platform).filter(Platform.name == platform_name).first()
    if not platform:
        # Автоматически создаём платформу (для гибкости)
        platform = Platform(name=platform_name)
        db.add(platform)
        db.flush()  # Получаем platform.id без коммита
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
        # 1. Сохраняем основное событие
        event = Event(
            project_id=event_data.project_id,
            action=event_data.action,
            timestamp=event_data.timestamp,
            metadata_=event_data.meta  # ← сохраняем как есть
        )
        db.add(event)
        db.flush()

        # 2. Сохраняем контекст (4НФ)
        if "platform" in event_data.context:
            ctx = EventContext(
                event_id=event.id,
                platform_id=get_platform_id(db, event_data.context["platform"]),
                language=event_data.context.get("language"),
                os_family=event_data.context.get("os_family"),
                browser_family=event_data.context.get("browser_family"),
                browser_version=event_data.context.get("browser_version")
            )
            db.add(ctx)

        # 3. Сохраняем URL
        if "page_url" in event_data.meta:  # ← проверяем в meta
            url = EventUrl(
                event_id=event.id,
                page_url=event_data.meta.get("page_url"),      # ← meta, не metadata!
                page_path=event_data.meta.get("page_path"),
                domain=event_data.meta.get("domain")
            )
            db.add(url)

        # 4. Сохраняем ошибку
        if "error_message" in event_data.meta:  # ← проверяем в meta
            err = EventError(
                event_id=event.id,
                error_message=event_data.meta.get("error_message"),  # ← meta!
                error_stack=event_data.meta.get("error_stack"),
                error_line=event_data.meta.get("error_line"),
                error_column=event_data.meta.get("error_column"),
                error_file=event_data.meta.get("error_file")
            )
            db.add(err)

        db.commit()
        
        # 5. Ставим задачу в Celery
        from src.workers.celery_app import celery_app
        celery_app.send_task('src.workers.tasks.process_event', args=[str(event.id)])

        return {"id": event.id}
    
    except Exception as e:
        db.rollback()
        logger.exception("Ошибка при обработке события")
        raise HTTPException(status_code=500, detail=str(e))