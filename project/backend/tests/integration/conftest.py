"""Фикстуры API: PostgreSQL через TEST_DATABASE_URL (см. tests/conftest.py)."""
from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def _require_test_db():
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip(
            "Нет TEST_DATABASE_URL. Пример: "
            "postgresql://postgres:postgres@127.0.0.1:5432/monitoring_test"
        )


@pytest.fixture(scope="session")
def engine():
    _require_test_db()
    url = os.environ["TEST_DATABASE_URL"]
    e = create_engine(url, pool_pre_ping=True)
    from src.core.database import Base

    import src.core.models  # noqa: F401 — регистрация таблиц в metadata

    try:
        Base.metadata.drop_all(e)
        Base.metadata.create_all(e)
    except (ProgrammingError, OperationalError) as exc:
        low = str(exc).lower()
        if "invalid dsn" in low or "invalid connection" in low:
            raise AssertionError(
                "TEST_DATABASE_URL не парсится: часто это кириллица в пароле (например буквально "
                "«ВАШ_ПАРОЛЬ» из примера) или пробелы в keyword-DSN без кавычек. "
                "Возьмите POSTGRES_PASSWORD из project/docker/.env и задайте URI, например: "
                "postgresql://postgres:<пароль>@127.0.0.1:5432/monitoring_test "
                "Если в пароле спецсимволы — закодируйте: urllib.parse.quote_plus."
            ) from exc
        raise
    yield e
    e.dispose()


def _truncate_all(conn):
    from src.core.database import Base

    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if names:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session_committed(engine):
    """Сессия для реальных commit() из эндпоинтов; таблицы чистятся до и после теста."""
    with engine.begin() as conn:
        _truncate_all(conn)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    with engine.begin() as conn:
        _truncate_all(conn)


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch):
    monkeypatch.setattr(
        "src.workers.celery_app.celery_app.send_task",
        lambda *a, **k: None,
    )
    m = MagicMock()
    m.delay = MagicMock(return_value=None)
    monkeypatch.setattr("src.workers.tasks.process_log_file", m)


@pytest.fixture
def client(engine, db_session_committed):
    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.core.database import get_db

    def override_get_db():
        try:
            yield db_session_committed
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_project_id(db_session_committed):
    from src.core.models import Project

    pid = uuid.uuid4()
    p = Project(id=pid, name="pytest project", description=None, is_active=True)
    db_session_committed.add(p)
    db_session_committed.commit()
    return pid


@pytest.fixture
def sample_project_with_api_key(db_session_committed, monkeypatch):
    monkeypatch.setenv("COLLECTOR_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("API_KEY_PEPPER", "test-pepper")

    from src.api.auth import hash_api_key
    from src.core.models import ApiKey, Project

    pid = uuid.uuid4()
    raw_key = "pytest-secret-api-key"
    p = Project(id=pid, name="pytest secured", description=None, is_active=True)
    db_session_committed.add(p)
    db_session_committed.flush()
    row = ApiKey(
        project_id=pid,
        name="test",
        hashed_key=hash_api_key(raw_key),
        is_revoked=False,
    )
    db_session_committed.add(row)
    db_session_committed.commit()
    return pid, raw_key
