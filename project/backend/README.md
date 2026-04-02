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

Переменные окружения: см. `src/core/config.py` и шаблон `project/docker/.env.example`.

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

Страницы: `/` — лендинг, `/register` — проект, `/docs/sdk` — инструкции SDK, **`/docs/demos`** — полные тексты демо из `examples/sdk-demos`, `/docs` — Swagger.

## Celery и бот

```bash
celery -A src.workers.celery_app.celery_app worker --loglevel=info
celery -A src.workers.celery_app.celery_app beat --loglevel=info
python -m src.services.telegram_bot
```

**Beat** по расписанию: еженедельный отчёт (понедельник 08:00 UTC), ежедневная очистка старых данных (03:20 UTC).

## Анализ ошибок для Telegram (Open WebUI)

Коллектор, воркер и бот шлют **POST** на OpenAI-совместимый API (часто `/api/chat/completions` у Open WebUI). Модель задаётся в интерфейсе Open WebUI (например Ollama на том же ПК).

| Переменная | Значение |
|------------|----------|
| `ERROR_ANALYSIS_BACKEND` | `open_webui` (по умолчанию) или `none` (без ИИ) |
| `OPEN_WEBUI_BASE_URL` | Например `http://127.0.0.1:3000` или `http://host.docker.internal:3000` из compose |
| `OPEN_WEBUI_MODEL` | Имя модели **как в Open WebUI** |
| `OPEN_WEBUI_API_KEY` | Если включена авторизация API в Open WebUI |
| `OPEN_WEBUI_CHAT_COMPLETIONS_PATH` | По умолчанию `/api/chat/completions` |
| `OPEN_WEBUI_MAX_TOKENS` | По умолчанию **512** |
| `OPEN_WEBUI_TIMEOUT_SEC` | По умолчанию **180** |
| `OPEN_WEBUI_REQUEST_JSON_OBJECT` | При ошибках API попробуйте `false` |

## Хранение данных и автоочистка

По умолчанию **Celery beat** раз в сутки удаляет записи старше `DATA_RETENTION_DAYS` и «осиротевшие» группы ошибок (без событий и без привязанных логов).

| Переменная | Значение |
|------------|----------|
| `DATA_RETENTION_ENABLED` | `true` / `false` |
| `DATA_RETENTION_DAYS` | По умолчанию **365** (ограничение в коде: от 30 до 1825 дней) |

Удаляются: строки в `log_files` и `events` с `created_at` до порога; затем строки в `error_groups`, на которые больше нет ссылок из `events` и `log_files`.

## Тесты

```bash
cd project/backend
pytest tests/ -q
```

## Поведение Telegram-бота

- **`/stats`**, **`/report`** — в чате проекта (`projects.telegram_chat_id`).
- **`/task`** с UUID — в группе только задачи того же проекта.
