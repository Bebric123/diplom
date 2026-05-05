# Error Monitor

Система сбора ошибок и логов из приложений: **коллектор** (FastAPI), **PostgreSQL**, **Redis/Celery**, **Telegram-бот** с кнопками «взять в работу» / «решено», краткий анализ ошибок через **[Open WebUI](https://github.com/open-webui/open-webui)** (HTTP к вашей модели, настроенной в UI). На сайте коллектора — инструкции SDK, **галерея полного кода демо** (`/docs/demos`), автоочистка старых событий и логов (по умолчанию год, настраивается).

Репозиторий: [github.com/Bebric123/diplom](https://github.com/Bebric123/diplom).

## Быстрый старт

**Docker (рекомендуется):** не обязательно клонировать весь git — достаточно [ZIP с GitHub](https://github.com/Bebric123/diplom/archive/refs/heads/main.zip), **`git clone --depth 1`** или sparse-checkout; см. [project/docker/QUICK_INSTALL.md](project/docker/QUICK_INSTALL.md).

```bash
git clone --depth 1 https://github.com/Bebric123/diplom.git
cd diplom
```

Дальше — стек через Docker (см. [project/docker/README.md](project/docker/README.md)):

```bash
cd project/docker
copy .env.example .env   # Windows; Linux/macOS: cp .env.example .env — затем заполните
docker compose up -d --build
```

Откройте [http://127.0.0.1:8000](http://127.0.0.1:8000) — главная, [http://127.0.0.1:8000/register](http://127.0.0.1:8000/register) — регистрация проекта (`project_id`, API-ключ, **Telegram chat id** для алертов).

## Структура репозитория

- **[project/backend](project/backend/README.md)** — коллектор (FastAPI), `/`, `/register`, `/docs/sdk`, `/docs/demos`, Telegram-бот, Celery-воркеры.  
- **[project/docker](project/docker/README.md)** — сборка образа и `docker-compose`: backend, worker, beat, bot, Postgres, Redis; по желанию профиль бэкапа БД.  
- **[project/sdk-python](project/sdk-python)** — пакет `error-monitor-sdk` (Python).  
- **[project/sdk-js](project/sdk-js)** — пакет `error-monitor-sdk` (Node.js).  
- **[project/sdk-php](project/sdk-php)** — Composer-пакет для PHP.  
- **[examples/sdk-demos](examples/sdk-demos/README.md)** — демо: Python, Node, PHP, React/Vite, Vue/Vite, `fetch` в браузере.

**Секреты:** файлы `.env` не коммитятся (см. корневой `.gitignore` и `project/.gitignore`); для Docker копируйте `project/docker/.env.example` в `.env` и заполните переменные.

Установка SDK из клона:

```bash
pip install ./project/sdk-python
# или без клона целиком:
pip install "git+https://github.com/Bebric123/diplom.git#subdirectory=project/sdk-python"
```

## Документация в браузере

После запуска: **SDK** — [http://127.0.0.1:8000/docs/sdk](http://127.0.0.1:8000/docs/sdk), **код всех демо** — [http://127.0.0.1:8000/docs/demos](http://127.0.0.1:8000/docs/demos), **OpenAPI** — [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Telegram

- Алерты уходят в чат, указанный при регистрации проекта.
- Команды **`/stats`** и **`/report`** в боте считают метрики **только по этому проекту** (нужно вызывать в том же чате, что привязан к проекту). В личке боту проект не сопоставить — команды попросят написать из группы.

## Анализ ошибок и хранение

**Open WebUI:** `OPEN_WEBUI_BASE_URL`, `OPEN_WEBUI_MODEL`, отключение ИИ — `ERROR_ANALYSIS_BACKEND=none`. Подробнее — [project/backend/README.md](project/backend/README.md) и [project/docker/README.md](project/docker/README.md).

**Ретенция:** `DATA_RETENTION_DAYS` (например 180 или 365), `DATA_RETENTION_ENABLED=false` — чтобы отключить фоновую очистку.

## Обслуживание, тесты, логи

Команды выполняйте из каталога **`project/docker`**, пока стек поднят через `docker compose`, или из **`project/backend`** для pytest и `alembic` на локальной БД.

- **`docker compose ps`** — список сервисов и портов.  
- **`docker compose logs -f backend`** / **`docker compose logs -f worker`** — логи API и Celery в реальном времени.  
- **`docker compose down`** — остановка контейнеров (данные Postgres в именованном volume обычно сохраняются).  
- **`docker compose down -v`** — то же, плюс удаление volume’ов из compose: **сброс данных PostgreSQL** в Docker.  
- **`docker compose exec redis redis-cli -n 0 FLUSHDB`** — очистить Redis (брокер/результаты для этого стека).  
- **`docker compose exec worker celery -A src.workers.celery_app.celery_app purge -f`** — очистить очередь задач Celery.  
- **`cd project/backend` → `pytest tests/ -q`** — тесты бэкенда (интеграция — с маркером и `TEST_DATABASE_URL`, см. [project/backend/README.md](project/backend/README.md)).  
- Подробнее по переменным Docker, бэкапу БД и сети: [project/docker/README.md](project/docker/README.md). Полный перечень демо: [examples/sdk-demos/README.md](examples/sdk-demos/README.md).  

## Лицензия и дипломный контекст

Проект учебный; перед продакшеном проверьте секреты, CORS, TLS и политику хранения данных.
