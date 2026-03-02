# backend/src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

# Читаем URL из .env
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/Monitoring")

# Синхронный движок (для Celery и большинства операций)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    echo=False  # включите для отладки
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency для FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()