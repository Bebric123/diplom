# Docker Compose — Error Monitor

Запуск коллектора, воркера Celery, планировщика (beat), Telegram-бота, PostgreSQL и Redis одной командой.

## Подготовка

1. Клонируйте репозиторий:

   ```bash
   git clone https://github.com/Bebric123/diplom.git
   cd diplom/project/docker
   ```

2. Создайте файл **`.env`** в этом каталоге (`project/docker/`). Задайте как минимум:

   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   - `DATABASE_URL` — строка SQLAlchemy на сервис `db` из compose (см. существующий шаблон в репозитории, если есть)
   - `REDIS_URL` — на сервис `redis`
   - `TELEGRAM_BOT_TOKEN` — токен бота для уведомлений и кнопок
   - при включённой проверке ключей: `COLLECTOR_REQUIRE_API_KEY`, при необходимости `API_KEY_PEPPER`
   - `CORS_ALLOW_ORIGINS` — для запросов с фронта (или `*` только для разработки)

Точный список переменных смотрите в `project/backend/src/core/config.py` и в комментариях к вашему `.env`.

## Запуск

```bash
cd project/docker
docker compose up -d --build
```

API: [http://127.0.0.1:8000](http://127.0.0.1:8000), health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Резервные копии PostgreSQL

Сервис **`db-backup`** в профиле `backup` периодически делает `pg_dump` в volume `pg_backups` (скрипт `scripts/pg_backup_loop.sh`, старше 14 дней удаляются).

```bash
docker compose --profile backup up -d db-backup
```

Интервал задаётся переменной `BACKUP_INTERVAL_SEC` (по умолчанию сутки).

## Сборка контекста

`Dockerfile.backend` ожидает контекст **`project/`** (родитель текущей папки): в `docker-compose.yml` указано `context: ..`. Запускайте команды из **`project/docker`**, а не из корня репозитория без правки путей.
