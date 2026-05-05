from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@db:5432/Monitoring"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "Monitoring"

    # Анализ ошибок: open_webui (HTTP к Open WebUI) | none
    error_analysis_backend: str = "open_webui"
    open_webui_base_url: str = "http://host.docker.internal:3000"
    open_webui_chat_completions_path: str = "/api/chat/completions"
    open_webui_api_key: str = ""
    open_webui_model: str = ""
    # Локальные модели (LM Studio и т.д.) нередко отвечают дольше 3 минут
    open_webui_timeout_sec: float = 420.0
    open_webui_max_tokens: int = 1024
    # Выше 0.05 — меньше копий одного и того же ответа; 0.15–0.3 обычно норм для детализации
    open_webui_temperature: float = Field(0.22, ge=0.0, le=2.0)
    # off — только промпт; json_object / json_schema — API response_format (LM Studio чаще 400 на json_object → off или json_schema)
    open_webui_response_format: str = "off"
    # Qwen / YaRN: в конец промпта дописывается «/no_think» — отключить внутренний reasoning, быстрее JSON
    open_webui_no_think: bool = True

    # Хранение: Celery beat — время запуска очистки (UTC) и N дней хранения
    data_retention_enabled: bool = True
    data_retention_days: int = 365
    data_retention_cron_hour: int = Field(3, ge=0, le=23, description="Час UTC для purge (crontab)")
    data_retention_cron_minute: int = Field(20, ge=0, le=59, description="Минута UTC")

    # Telegram: токен бота обязателен. chat_id — опциональный fallback для sendDocument без явного чата
    # (еженедельные отчёты уходят в projects.telegram_chat_id по каждому проекту).
    telegram_bot_token: str
    telegram_chat_id: Optional[str] = None

    # Отчёты / статистика (HTTP); если задан — нужен Bearer или X-Reports-Token
    reports_api_token: Optional[str] = None
    # Периодические отчёты в чаты проектов (Celery beat) + окно в днях для /stats, /report
    weekly_report_enabled: bool = True
    stats_report_range_days: int = Field(
        7,
        ge=1,
        le=365,
        description="Сколько дней в сводку в боте и в периодическом Excel-отчёте",
    )
    # Расписание beat: cron (как раньше: пн 08:00 UTC) либо каждые N суток (timedelta)
    stats_report_beat_mode: Literal["cron", "interval"] = "cron"
    stats_report_beat_interval_days: int = Field(7, ge=1, le=365, description="Если mode=interval — сработка каждые N дней")
    stats_report_beat_cron_minute: int = Field(0, ge=0, le=59, description="Если mode=cron — UTC")
    stats_report_beat_cron_hour: int = Field(8, ge=0, le=23, description="Если mode=cron — UTC")
    stats_report_beat_cron_day_of_week: str = Field("mon", description="Если mode=cron: mon/tue/… или 0-6 (sun=0)")
    # Троттлинг уведомлений в Telegram по серьёзности: секунды до повторного пуша в ту же error_group (тот же severity)
    alert_throttle_low_sec: int = Field(3600, ge=0)
    alert_throttle_medium_sec: int = Field(1800, ge=0)
    alert_throttle_high_sec: int = Field(900, ge=0)
    alert_throttle_critical_sec: int = Field(300, ge=0)
    alert_throttle_default_sec: int = Field(1800, ge=0, description="Секунды для иной/неизвестной серьёзности")

    # Collector HTTP API
    collector_require_api_key: bool = False
    api_key_pepper: str = ""
    cors_allow_origins: str = ""
    trusted_hosts: str = ""
    hsts_max_age: Optional[int] = None

    def cors_origins_list(self) -> List[str]:
        raw = (self.cors_allow_origins or "").strip()
        if not raw:
            return []
        return [o.strip() for o in raw.split(",") if o.strip()]

    def trusted_hosts_list(self) -> List[str]:
        raw = (self.trusted_hosts or "").strip()
        if not raw:
            return []
        return [h.strip() for h in raw.split(",") if h.strip()]



def get_settings() -> Settings:
    return Settings()