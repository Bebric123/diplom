# Демо и ручная проверка SDK

Коллектор (FastAPI) по умолчанию: `http://127.0.0.1:8000`. Запустите стек (`docker-compose` в `project/docker`).

**Регистрация проекта:** откройте в браузере `http://127.0.0.1:8000/register` — выберите стек, укажите **Telegram chat id** группы/чата, куда должен писать бот; получите **project_id** и **API-ключ** для SDK. Уведомления об ошибках уходят только в указанный чат.

Для ручного сида без формы можно выполнить `project/backend/db/seed_collector_security.sql` (демо-ключ `dev-demo-ingest-key`; для алертов в Telegram у демо-проекта всё равно нужно выставить `telegram_chat_id` в БД или зарегистрировать проект через форму).

Переменные окружения (опционально):

- `MONITOR_URL` — URL коллектора (по умолчанию `http://127.0.0.1:8000`)
- `MONITOR_PROJECT_ID` — UUID проекта (по умолчанию `00000000-0000-4000-8000-000000000001`)
- `MONITOR_API_KEY` — секрет для коллектора, если включён `COLLECTOR_REQUIRE_API_KEY` (тот же ключ, что в сиде: `dev-demo-ingest-key`)

### Где создавать `.env` для демо

| Что запускаете | Файл | Переменные |
|----------------|------|------------|
| **Docker-коллектор** (бэкенд, бот, БД) | `project/docker/.env` | `TELEGRAM_BOT_TOKEN`, `POSTGRES_*`, `COLLECTOR_REQUIRE_API_KEY`, `CORS_ALLOW_ORIGINS` и т.д. — как в шаблоне проекта |
| **React / Vue (Vite)** | `examples/sdk-demos/frontend/react-vite/.env` или `.../vue-vite/.env` | Скопируйте из `.env.example` в том же каталоге. Имена только с префиксом **`VITE_`** (`VITE_MONITOR_URL`, `VITE_MONITOR_PROJECT_ID`, `VITE_MONITOR_API_KEY`) |
| **Python, Node, PHP** в `examples/sdk-demos/` | Отдельного автоподхватываемого `.env` нет | Читают **переменные окружения ОС** (`MONITOR_URL`, `MONITOR_PROJECT_ID`, `MONITOR_API_KEY`). Задайте в терминале перед запуском или используйте общий шаблон ниже |

Общий шаблон для Python/Node/PHP (скопируйте в `examples/sdk-demos/.env` и подставьте значения — файл **сам по себе скриптами не читается**, это шпаргалка; в PowerShell можно выставить вручную):

```text
MONITOR_URL=http://127.0.0.1:8000
MONITOR_PROJECT_ID=ваш-uuid-с-страницы-register
MONITOR_API_KEY=ваш-ключ
```

Пример для **PowerShell** из каталога `examples/sdk-demos/python`:

```powershell
$env:MONITOR_URL="http://127.0.0.1:8000"
$env:MONITOR_PROJECT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
$env:MONITOR_API_KEY="ваш-ключ"
python 01_minimal_client.py
```

**Безопасность коллектора (переменные в `.env` бэкенда):** `COLLECTOR_REQUIRE_API_KEY=true` — требовать `Authorization: Bearer …` или `X-Api-Key` для `/track`, `/logs/upload` и чтения логов; `API_KEY_PEPPER` — необязательная строка, добавляемая перед хешированием ключа (тогда в БД храните SHA256(pepper+ключ) в hex); `CORS_ALLOW_ORIGINS` — список через запятую или `*`; `TRUSTED_HOSTS` — доверенные `Host` заголовки; `HSTS_MAX_AGE` — если задан (секунды), отдаётся заголовок HSTS; `GIGACHAT_VERIFY_SSL=true` — проверять TLS к GigaChat (по умолчанию выключено из‑за окружений с кастомными ЦС).

## Python (`examples/sdk-demos/python`)

```bash
cd examples/sdk-demos/python
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python 01_minimal_client.py
python 02_fastapi_demo.py   # слушает :8010
```

Для отдельных фреймворков можно ставить только нужные пакеты (см. комментарии в `requirements.txt`).

### Django MVP (`examples/sdk-demos/python/django_mvp`)

Минимальный проект: `init_monitor` в `MonitoringConfig.ready()`, в `MIDDLEWARE` указан **класс** `error_monitor_sdk.integrations.django.DjangoMonitoringMiddleware` (не экземпляр из `enable_django_integration()`).

**Важно:** `MONITOR_URL` — это URL **коллектора** (часто `http://127.0.0.1:8000`), а не адрес `runserver` этого демо (`:8030`). Если указать порт Django, SDK будет слать `POST /track` на само приложение → 404; в SDK пути `/track` и `/logs/upload` исключены из middleware, чтобы не было рекурсивного шторма запросов.

```powershell
cd examples/sdk-demos/python
pip install -r requirements.txt   # или: pip install django -e ../../../project/sdk-python
cd django_mvp
$env:MONITOR_URL="http://127.0.0.1:8000"
$env:MONITOR_PROJECT_ID="ваш-uuid"
$env:MONITOR_API_KEY="ваш-ключ"   # если на коллекторе включён API key
python manage.py migrate
python manage.py runserver 8030
```

- `http://127.0.0.1:8030/health/` — ответ `{"ok": true}` (путь в исключениях middleware, без лишних событий).
- `http://127.0.0.1:8030/boom/` — исключение уходит в коллектор через middleware.

## Node.js (`examples/sdk-demos/nodejs`)

```bash
cd examples/sdk-demos/nodejs
npm install
node 01_minimal.cjs
node 02_express_demo.cjs    # :8020
node 03_fastify_demo.cjs    # :8021
node 04_upload_log.cjs   # sendLogFile() из JS SDK → /logs/upload
```

## PHP (`examples/sdk-demos/php`)

Нужны PHP ≥ 8.1 и расширения `curl`, `json`. SDK подключается как path-зависимость на `project/sdk-php`; Slim — только для `03_slim_demo.php`.

```bash
cd examples/sdk-demos/php
composer install
php 01_minimal.php
php -S 127.0.0.1:8015 02_builtin_server.php   # /health, /ok, /boom
php -S 127.0.0.1:8016 03_slim_demo.php        # Slim 4, те же маршруты
php 04_upload_log.php                         # send_log_file() → /logs/upload
```

Переменные окружения те же, что в начале README (`MONITOR_URL`, `MONITOR_PROJECT_ID`, `MONITOR_API_KEY`). Загрузка логов: **`send_log_file()`** / `ErrorMonitor\Logs::sendLogFile()` с проверкой лимитов коллектора (размер контента, длины полей, `lines_sent`).

**Laravel:** отдельного «одного файла» в репозитории нет — полный скелет Laravel тяжёлый для git. Пошаговая инструкция и фрагменты кода: [`php/laravel-demo/README.md`](php/laravel-demo/README.md) (`MonitorServiceProvider` уже в SDK, нужны `composer`, `bootstrap/providers.php`, `bootstrap/app.php` и `.env`).

## React, Vue, Angular и текущие JS-демо

**Node (`examples/sdk-demos/nodejs`)** — только сервер (Express/Fastify и т.д.), не SPA.

**Проверка фронта с SDK:** каталог **`examples/sdk-demos/frontend`** — готовые **React + Vite** и **Vue 3 + Vite** (`npm run dev`, см. раздел ниже и [frontend/README.md](frontend/README.md)). В коде используется `import * as MonitorSdk from 'error-monitor-sdk'` из‑за CommonJS в пакете.

**Angular** — отдельного модуля в SDK нет: свой `ErrorHandler` + `getClient().captureException` и при необходимости идеи из `browser.js`.

**`browser/fetch_track_demo.html`** — только ручной `fetch`, без lifecycle фреймворков.

## Браузер (`examples/sdk-demos/browser`)

Файл `fetch_track_demo.html` шлёт JSON на `/track` через `fetch`. Из-за CORS страницу нужно открывать **не** как `file://`: поднимите статику, например `npx serve .` в каталоге `browser`, и временно разрешите CORS на коллекторе для вашего origin (или проксируйте API на тот же хост).

## Фронтенд: React и Vue + Vite (`examples/sdk-demos/frontend`)

Полноценная проверка SDK в браузере с **Error Boundary** (React) и **errorHandler** (Vue 3):

```bash
cd examples/sdk-demos/frontend/react-vite && npm install && npm run dev   # порт 5173
cd examples/sdk-demos/frontend/vue-vite   && npm install && npm run dev   # порт 5174
```

Подробности, `.env` с префиксом `VITE_`, CORS и заглушки `os` / `setImmediate`: **[frontend/README.md](frontend/README.md)**.

Интеграция `integrations/browser.js` в демо подключается после `initMonitor`; пакет SDK по-прежнему CommonJS — в коде демо используется `import * as MonitorSdk from 'error-monitor-sdk'`.

## Новые интеграции в SDK

**Python:** `starlette.py`, `quart.py`, `litestar.py` (фабрика `make_litestar_middleware()` для Litestar 2).  
**JavaScript:** `integrations/fastify.js`; фронт: `integrations/react.js`, `integrations/vue.js`.

Исправлены пути `require` в `express.js` и `browser.js` (теперь `../index`).
