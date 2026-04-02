# Docker Compose — Error Monitor

Запуск коллектора, воркера Celery, планировщика (beat), Telegram-бота, PostgreSQL и Redis одной командой.

## Подготовка

1. Получите код (любой вариант):
   - **ZIP** с GitHub или **`git clone --depth 1`** — см. [QUICK_INSTALL.md](QUICK_INSTALL.md).
   - Классический клон: `git clone https://github.com/Bebric123/diplom.git` → `cd diplom/project/docker`.

2. Создайте файл **`.env`** в этом каталоге (`project/docker/`). Шаблон: **`.env.example`**. Задайте как минимум:

   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   - `DATABASE_URL` — на сервис `db` из compose
   - `REDIS_URL` — на сервис `redis`
   - `TELEGRAM_BOT_TOKEN`
   - при включённой проверке ключей: `COLLECTOR_REQUIRE_API_KEY`, при необходимости `API_KEY_PEPPER`
   - `CORS_ALLOW_ORIGINS` — для запросов с фронта (или `*` только для разработки)
   - **Open WebUI:** `OPEN_WEBUI_BASE_URL` (часто `http://host.docker.internal:3000` при `-p 3000:8080` на хосте), `OPEN_WEBUI_MODEL` — как в веб-интерфейсе. В compose для **`backend`**, **`worker`**, **`bot`** задано **`extra_hosts: host.docker.internal:host-gateway`** (Linux; на Docker Desktop имя обычно уже есть).
   - **Ретенция данных:** `DATA_RETENTION_ENABLED`, `DATA_RETENTION_DAYS` (по умолчанию год) — ежедневная задача beat удаляет старые события и загруженные логи.

Точный список переменных: `project/backend/src/core/config.py`.

## Запуск

```bash
cd project/docker
docker compose up -d --build
```

API: [http://127.0.0.1:8000](http://127.0.0.1:8000), **код демо:** [http://127.0.0.1:8000/docs/demos](http://127.0.0.1:8000/docs/demos), health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

### Celery worker

`CELERY_WORKER_CONCURRENCY` (по умолчанию **1**). ИИ выполняется на хосте (Open WebUI); при нагрузочном тесте без ИИ: **`ERROR_ANALYSIS_BACKEND=none`**.

### Ошибка `Temporary failure in name resolution` / `redis:6379`

В `.env` должен быть **`REDIS_URL=redis://redis:6379/0`** (имя сервиса из compose, не `localhost`). При **Error -3 connecting to redis** на Docker Desktop: `docker compose restart redis worker`.

## Резервные копии PostgreSQL

```bash
docker compose --profile backup up -d db-backup
```

Интервал: `BACKUP_INTERVAL_SEC` (по умолчанию сутки).

## Сборка контекста

`Dockerfile.backend` ожидает контекст **`project/`**: в `docker-compose.yml` указано `context: ..`. Запускайте команды из **`project/docker`**.

## Сеть и ИИ

- Тексты инцидентов для Telegram уходят **HTTP** на **`OPEN_WEBUI_BASE_URL`**. Маршрут дальше (Ollama, облако и т.д.) задаётся в Open WebUI.
- **Telegram Bot API** требует исходящий HTTPS до серверов Telegram.

## Нагрузочный тест

**`ERROR_ANALYSIS_BACKEND=none`** отключает вызовы ИИ. Очередь Celery: `docker compose exec worker celery -A src.workers.celery_app.celery_app purge -f`.

## Разовая очистка Redis

```bash
docker compose exec redis redis-cli -n 0 FLUSHDB
```

(сбрасывает брокер и результаты Celery для этого compose.)
