# backend/src/core/database.py
import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# Читаем URL из .env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/Monitoring")

Base = declarative_base()

_engine = None
_session_factory = None


def get_engine():
    """Создаёт движок при первом обращении (удобно для pytest без живой БД на этапе импорта)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=30,
            echo=False,
        )
    return _engine


def _session_maker():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _session_factory


class _SessionLocalProxy:
    def __call__(self, *args: Any, **kwargs: Any):
        return _session_maker()(*args, **kwargs)


SessionLocal = _SessionLocalProxy()


class _EngineProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)


engine = _EngineProxy()


def get_db():
    """Dependency для FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
