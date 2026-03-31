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
   - **`LOCAL_LLM_GGUF_PATH`** — путь **внутри контейнера**, каталог **`./models` → `/models`** смонтирован у **`backend`**, **`worker`** и **`bot`** (бот при нажатии кнопок заново вызывает анализ и правит текст сообщения). Положите `.gguf` в **`project/docker/models/`** и укажите имя файла, например `LOCAL_LLM_GGUF_PATH=/models/имя_файла.gguf`. Без файла — запасной текст в уведомлении; без ИИ: `ERROR_ANALYSIS_BACKEND=none`

Точный список переменных смотрите в `project/backend/src/core/config.py` и в комментариях к вашему `.env`.

Если при `docker compose build` не находится готовый wheel для `llama-cpp-python`, добавьте в `Dockerfile.backend` пакеты сборки (`cmake`, `build-essential`) или зафиксируйте версию образа с подходящим wheel под вашу платформу.

## Запуск

```bash
cd project/docker
docker compose up -d --build
```

API: [http://127.0.0.1:8000](http://127.0.0.1:8000), health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

### Celery worker и нагрузка / LLM

Воркер запускается с **`CELERY_WORKER_CONCURRENCY`** (по умолчанию **1** в `docker-compose.yml`). При **локальном GGUF** каждый дочерний процесс Celery может поднять свою копию модели в памяти: concurrency как число ядер при ограниченной RAM Docker часто даёт **`WorkerLostError: signal 9 (SIGKILL)`** (OOM) и сопутствующие сбои PostgreSQL. Для чистого нагрузочного теста приёма событий без ИИ можно выставить **`ERROR_ANALYSIS_BACKEND=none`** и при необходимости осторожно поднять concurrency; с LLM оставляйте **1**, если не увеличиваете лимит памяти контейнера/хоста.

### Ошибка `Temporary failure in name resolution` / `redis:6379`

В `.env` для контейнеров должен быть **`REDIS_URL=redis://redis:6379/0`** (имя сервиса из `docker-compose.yml`, не `localhost`). Если воркер пишет **Error -3 connecting to redis** — чаще всего краткий сбой DNS у Docker Desktop (Windows): выполните `docker compose restart redis worker` или перезапустите Docker. В коде Celery включены повторные попытки подключения к брокеру.

## Резервные копии PostgreSQL

Сервис **`db-backup`** в профиле `backup` периодически делает `pg_dump` в volume `pg_backups` (скрипт `scripts/pg_backup_loop.sh`, старше 14 дней удаляются).

```bash
docker compose --profile backup up -d db-backup
```

Интервал задаётся переменной `BACKUP_INTERVAL_SEC` (по умолчанию сутки).

## Сборка контекста

`Dockerfile.backend` ожидает контекст **`project/`** (родитель текущей папки): в `docker-compose.yml` указано `context: ..`. Запускайте команды из **`project/docker`**, а не из корня репозитория без правки путей.
