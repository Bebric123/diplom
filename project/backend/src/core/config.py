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

    # GigaChat
    gigachat_auth_key: str
    gigachat_verify_ssl: bool = False

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