# Backend (коллектор Error Monitor)

FastAPI-сервис приёма событий и логов, регистрация проектов, отчёты и Telegram-бот.

## Требования

- Python 3.11+ (как в Docker-образе)
- PostgreSQL 15+
- Redis (для Celery)

## Установка из клона репозитория

Из корня монорепозитория:

```bash
cd project/backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

Переменные окружения: см. использование в `src/core/config.py` и шаблон `project/docker/.env`. Минимум для локального запуска без Docker — строка подключения к PostgreSQL и при необходимости `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `COLLECTOR_REQUIRE_API_KEY`, `API_KEY_PEPPER`.

## Миграции

```bash
cd project/backend
alembic upgrade head
```

## Запуск API

```bash
cd project/backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Страницы: `/` — лендинг, `/register` — создание проекта, `/docs/sdk` — инструкции по SDK, `/docs` — Swagger.

## Celery и бот

В отдельных терминалах (из `project/backend`, с тем же `.env` / переменными):

```bash
celery -A src.workers.celery_app.celery_app worker --loglevel=info
celery -A src.workers.celery_app.celery_app beat --loglevel=info
python -m src.services.telegram_bot
```

## Тесты

```bash
cd project/backend
pytest tests/ -q
```

Часть интеграционных тестов пропускается без настроенной тестовой БД (`TEST_DATABASE_URL`).

## Поведение Telegram-бота

- **`/stats`**, **`/report`** — только в чате, чей id совпадает с `projects.telegram_chat_id` (тот же чат, куда уходят алерты). Статистика и Excel фильтруются по `project_id` этого проекта.
- **`/task`** с UUID — в группе доступна только задача того же проекта; в личке — поиск по всей базе (удобство отладки).
