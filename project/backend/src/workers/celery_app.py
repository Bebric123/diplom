from celery import Celery
from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "monitoring_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks"]  # ← важно!
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
)

def get_celery_app():
    return celery_app