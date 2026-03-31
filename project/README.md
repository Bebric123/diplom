# Error Monitor — код проекта

Каталог **`project/`** содержит всё для запуска коллектора и SDK.

- **[backend](backend/README.md)** — FastAPI-приложение (`src/api/main.py`), шаблоны (`src/web/templates`), Celery-задачи, Telegram-бот.
- **[docker](docker/README.md)** — сборка образа и `docker-compose` для локального и серверного запуска.
- **sdk-python**, **sdk-js**, **sdk-php** — клиентские библиотеки для отправки событий (`POST /track`) и логов (`POST /logs/upload`).

Корневой обзор репозитория и клонирование с GitHub: [../README.md](../README.md).
