# backend/src/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/Monitoring"
    gigachat_auth_key: str 

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()