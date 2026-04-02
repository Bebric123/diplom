from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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
    open_webui_timeout_sec: float = 180.0
    open_webui_max_tokens: int = 512
    open_webui_request_json_object: bool = True

    # Хранение: ежедневная очистка событий и логов старше N дней (и «осиротевших» групп ошибок)
    data_retention_enabled: bool = True
    data_retention_days: int = 365

    # Telegram (токен бота обязателен; chat_id — опционально: для еженедельных отчётов в «общий» чат)
    telegram_bot_token: str
    telegram_chat_id: Optional[str] = None

    # Отчёты / статистика (HTTP); если задан — нужен Bearer или X-Reports-Token
    reports_api_token: Optional[str] = None
    weekly_report_enabled: bool = True

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

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()