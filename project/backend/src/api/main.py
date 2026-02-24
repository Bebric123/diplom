from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.models import Event, EventContext, EventUrl, EventError, Platform
from src.core.database import get_db
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

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
            metadata_=event_data.metadata
        )
        db.add(event)
        db.flush()  # Получаем event.id

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
        if "page_url" in event_data.meta:
            url = EventUrl(
                event_id=event.id,
                page_url=event_data.metadata.get("page_url"),
                page_path=event_data.metadata.get("page_path"),
                domain=event_data.metadata.get("domain")
            )
            db.add(url)

        # 4. Сохраняем ошибку
        if "error_message" in event_data.meta:
            err = EventError(
                event_id=event.id,
                error_message=event_data.metadata.get("error_message"),
                error_stack=event_data.metadata.get("error_stack"),
                error_line=event_data.metadata.get("error_line"),
                error_column=event_data.metadata.get("error_column"),
                error_file=event_data.metadata.get("error_file")
            )
            db.add(err)

        db.commit()
        
        # 5. Ставим задачу в Celery
        from workers.tasks import process_event
        process_event.delay(str(event.id))

        return {"id": event.id}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))