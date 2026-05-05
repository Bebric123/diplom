from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "monitoring_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks"]  # ← важно!
)


def _build_beat_schedule():
    s = get_settings()
    out = {}
    if s.weekly_report_enabled:
        if s.stats_report_beat_mode == "interval":
            sched = timedelta(days=s.stats_report_beat_interval_days)
        else:
            dow = (s.stats_report_beat_cron_day_of_week or "mon").strip()
            if dow.isdigit():
                sched = crontab(
                    minute=s.stats_report_beat_cron_minute,
                    hour=s.stats_report_beat_cron_hour,
                    day_of_week=int(dow),
                )
            else:
                sched = crontab(
                    minute=s.stats_report_beat_cron_minute,
                    hour=s.stats_report_beat_cron_hour,
                    day_of_week=dow,
                )
        out["stats-report"] = {
            "task": "src.workers.tasks.send_weekly_stats_report",
            "schedule": sched,
        }
    if s.data_retention_enabled:
        out["purge-old-monitoring-data"] = {
            "task": "src.workers.tasks.purge_old_monitoring_data",
            "schedule": crontab(
                hour=s.data_retention_cron_hour, minute=s.data_retention_cron_minute
            ),
        }
    return out


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
    # После рестартов Redis / глюков DNS Docker (Errno -3 name resolution)
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=100,
    result_backend_transport_options={
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },
    beat_schedule=_build_beat_schedule(),
)

def get_celery_app():
    return celery_app