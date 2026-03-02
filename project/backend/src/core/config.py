from pydantic_settings import BaseSettings
from typing import Optional

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
    
    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str
    
    # Разрешить лишние переменные (опционально, но рекомендуется для гибкости)
    class Config:
        env_file = ".env"
        extra = "ignore"  # ← ИГНОРИРОВАТЬ лишние переменные в .env

def get_settings():
    return Settings()