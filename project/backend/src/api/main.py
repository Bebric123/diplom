from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.models import Event, EventContext, EventUrl, EventError, Platform, LogFile, Project
from src.core.database import get_db
from pydantic import BaseModel, Field
import logging  
from typing import Optional, Dict, Any, List
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
    
class LogFileCreate(BaseModel):
    project_id: str
    filename: str
    content: str  # последние N строк
    lines_sent: int
    total_lines: Optional[int] = None
    server_name: Optional[str] = None
    service_name: Optional[str] = None
    environment: Optional[str] = "production"
    error_group_id: Optional[str] = None  # если привязано к ошибке
    metadata: Optional[Dict[str, Any]] = {}

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
    """
    Принимает последние N строк лог-файла
    """
    try:
        # Проверяем проект
        project = db.query(Project).filter(Project.id == log_data.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Сохраняем лог в БД
        log_file = LogFile(
            project_id=log_data.project_id,
            filename=log_data.filename,
            content=log_data.content,
            lines_sent=log_data.lines_sent,
            total_lines=log_data.total_lines,
            server_name=log_data.server_name,
            service_name=log_data.service_name,
            environment=log_data.environment,
            error_group_id=log_data.error_group_id,
            file_size=len(log_data.content.encode('utf-8')),
            file_path=f"/logs/{log_data.project_id}/{log_data.filename}"
        )
        
        db.add(log_file)
        db.commit()
        db.refresh(log_file)
        
        # Отправляем в Celery для анализа
        from src.workers.tasks import process_log_file
        process_log_file.delay(str(log_file.id))
        
        return {"id": str(log_file.id), "message": "Log file received successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading log file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs/{log_id}")
async def get_log(log_id: str, db: Session = Depends(get_db)):
    """Получить информацию о логе"""
    log_file = db.query(LogFile).filter(LogFile.id == log_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log not found")
    
    return LogFileResponse(
        id=str(log_file.id),
        filename=log_file.filename,
        lines_sent=log_file.lines_sent,
        total_lines=log_file.total_lines,
        created_at=log_file.created_at.isoformat(),
        server_name=log_file.server_name,
        service_name=log_file.service_name
    )

@app.get("/projects/{project_id}/logs")
async def list_project_logs(
    project_id: str, 
    limit: int = 50, 
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Список логов проекта"""
    logs = db.query(LogFile)\
        .filter(LogFile.project_id == project_id)\
        .order_by(LogFile.created_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
    
    return [
        LogFileResponse(
            id=str(log.id),
            filename=log.filename,
            lines_sent=log.lines_sent,
            total_lines=log.total_lines,
            created_at=log.created_at.isoformat(),
            server_name=log.server_name,
            service_name=log.service_name
        )
        for log in logs
    ]