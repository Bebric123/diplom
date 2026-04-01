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

    # Анализ ошибок в Telegram: local_gguf (локальный GGUF) | none (заглушка без ИИ)
    error_analysis_backend: str = "local_gguf"
    # Путь к .gguf: задавайте в .env (LOCAL_LLM_GGUF_PATH). В Docker — путь внутри контейнера (том).
    # На Windows в .env используйте прямые слэши: C:/Users/.../model.gguf — иначе \U в путях ломает разбор.
    local_llm_gguf_path: str = ""
    local_llm_n_ctx: int = 8192
    # Короткий ответ = меньше токенов на CPU/GPU; с JSON-грамматикой хватает сотен
    local_llm_max_tokens: int = 384
    local_llm_n_threads: int = 0
    local_llm_n_gpu_layers: int = 0
    # Снижает зацикливание на слабых квантах (IQ1 и т.п.); типично 1.1–1.25
    local_llm_repeat_penalty: float = 1.18
    # Ограничить вывод схемой JSON (llama.cpp grammar); сильно помогает против «простыней» вместо JSON
    local_llm_json_grammar: bool = True
    # Ещё сильнее ужимает max_tokens и лимит при грамматике (скорость на CPU); для очень длинных логов — false
    local_llm_fast_mode: bool = True

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