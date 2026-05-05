# Error Monitor — код проекта

Каталог **`project/`** содержит всё для запуска коллектора и SDK.

- **[backend](backend/README.md)** — FastAPI-приложение (`src/api/main.py`), шаблоны (`src/web/templates`), Celery-задачи, Telegram-бот.  
- **[docker](docker/README.md)** — сборка образа и `docker-compose` для локального и серверного запуска.  
- **sdk-python**, **sdk-js**, **sdk-php** — клиентские библиотеки для отправки событий (`POST /track`) и логов (`POST /logs/upload`).

**Git:** в корне репозитория и в `project/.gitignore` заданы игнорируемые пути (`.env`, venv, `__pycache__`, `node_modules`, кэш pytest и т.д.); при необходимости используйте шаблоны `project/docker/.env.example` и `.env.example` в подкаталогах демо.

Корневой обзор, команды обслуживания и ссылки: [../README.md](../README.md).
