# Error Monitor

Система сбора ошибок и логов из приложений: **коллектор** (FastAPI), **PostgreSQL**, **Redis/Celery**, **Telegram-бот** с кнопками «взять в работу» / «решено», краткий **локальный** анализ ошибок в уведомлениях (GGUF через `llama-cpp-python`, данные не уходят в облачные LLM).

Репозиторий: [github.com/Bebric123/diplom](https://github.com/Bebric123/diplom).

## Быстрый старт с GitHub

```bash
git clone https://github.com/Bebric123/diplom.git
cd diplom
```

Дальше проще всего поднять стек через Docker (см. [project/docker/README.md](project/docker/README.md)):

```bash
cd project/docker
# Скопируйте и заполните .env (см. README в том каталоге)
docker compose up -d --build
```

Откройте [http://127.0.0.1:8000](http://127.0.0.1:8000) — главная, [http://127.0.0.1:8000/register](http://127.0.0.1:8000/register) — регистрация проекта (`project_id`, API-ключ, **Telegram chat id** для алертов).

## Структура репозитория

| Путь | Назначение |
|------|------------|
| [project/backend](project/backend/README.md) | Коллектор API, веб-страницы (`/`, `/register`, `/docs/sdk`), бот, воркеры |
| [project/docker](project/docker/README.md) | `docker-compose`: backend, worker, beat, bot, Postgres, Redis; опционально бэкапы БД |
| [project/sdk-python](project/sdk-python) | Пакет `error-monitor-sdk` (Python) |
| [project/sdk-js](project/sdk-js) | Пакет `error-monitor-sdk` (Node.js) |
| [project/sdk-php](project/sdk-php) | Composer-пакет для PHP |
| [examples/sdk-demos](examples/sdk-demos/README.md) | Рабочие демо: Python, Node, PHP, React/Vite, Vue/Vite, `fetch` в браузере |

Установка SDK из клона:

```bash
pip install ./project/sdk-python
# или без клона целиком:
pip install "git+https://github.com/Bebric123/diplom.git#subdirectory=project/sdk-python"
```

## Документация в браузере

После запуска коллектора: **инструкции и примеры кода** — [http://127.0.0.1:8000/docs/sdk](http://127.0.0.1:8000/docs/sdk) (в т.ч. установка из GitHub, пути к `project/sdk-*`). **OpenAPI** — [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Telegram

- Алерты уходят в чат, указанный при регистрации проекта.
- Команды **`/stats`** и **`/report`** в боте считают метрики **только по этому проекту** (нужно вызывать в том же чате, что привязан к проекту). В личке боту проект не сопоставить — команды попросят написать из группы.

## Анализ ошибок в Telegram

Используется только **локальная** GGUF-модель (`LOCAL_LLM_GGUF_PATH`, см. `project/backend/README.md`); тексты ошибок для подписи в Telegram **не** отправляются во внешние LLM. Чтобы временно отключить ИИ, задайте `ERROR_ANALYSIS_BACKEND=none`.

## Лицензия и дипломный контекст

Проект учебный; перед продакшеном проверьте секреты, CORS, TLS и политику хранения данных.
