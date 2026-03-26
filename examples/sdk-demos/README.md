# Демо и ручная проверка SDK

Коллектор (FastAPI) по умолчанию: `http://127.0.0.1:8000`. Запустите стек (`docker-compose` в `project/docker`).

**Регистрация проекта:** откройте в браузере `http://127.0.0.1:8000/register` — выберите стек, укажите **Telegram chat id** группы/чата, куда должен писать бот; получите **project_id** и **API-ключ** для SDK. Уведомления об ошибках уходят только в указанный чат.

Для ручного сида без формы можно выполнить `project/backend/db/seed_collector_security.sql` (демо-ключ `dev-demo-ingest-key`; для алертов в Telegram у демо-проекта всё равно нужно выставить `telegram_chat_id` в БД или зарегистрировать проект через форму).

Переменные окружения (опционально):

- `MONITOR_URL` — URL коллектора (по умолчанию `http://127.0.0.1:8000`)
- `MONITOR_PROJECT_ID` — UUID проекта (по умолчанию `00000000-0000-4000-8000-000000000001`)
- `MONITOR_API_KEY` — секрет для коллектора, если включён `COLLECTOR_REQUIRE_API_KEY` (тот же ключ, что в сиде: `dev-demo-ingest-key`)

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

## Node.js (`examples/sdk-demos/nodejs`)

```bash
cd examples/sdk-demos/nodejs
npm install
node 01_minimal.cjs
node 02_express_demo.cjs    # :8020
node 03_fastify_demo.cjs    # :8021
node 04_upload_log.cjs   # sendLogFile() из JS SDK → /logs/upload
```

## React и Vue

Это не серверные фреймворки: отдельного «middleware», как у Express, нет. Нужны **Error Boundary** (React) и **глобальный errorHandler** (Vue), которые вызывают тот же клиент, что и `initMonitor` + `integrations/browser.js`.

**React** (`error-monitor-sdk/integrations/react`):

- Оберните дерево в `<MonitorErrorBoundary>` или используйте `withMonitorErrorBoundary(Comp)`.
- Плюс в корне приложения вызовите `enableBrowserIntegration()` из `integrations/browser` для `window.onerror` / `unhandledrejection`.

**Vue 3:** `installVue3Monitor(app)` после `createApp(...)`. **Vue 2:** `installVue2Monitor(Vue)` один раз при старте. Аналогично имеет смысл подключить браузерную интеграцию для ошибок вне Vue.

## Браузер (`examples/sdk-demos/browser`)

Файл `fetch_track_demo.html` шлёт JSON на `/track` через `fetch`. Из-за CORS страницу нужно открывать **не** как `file://`: поднимите статику, например `npx serve .` в каталоге `browser`, и временно разрешите CORS на коллекторе для вашего origin (или проксируйте API на тот же хост).

Интеграция `integrations/browser.js` рассчитана на сборку под браузер (например webpack) или на среду с `require`; текущий Node-SDK использует модуль `os` — для чистого браузера удобнее демо через `fetch` или отдельный лёгкий бандл.

## Новые интеграции в SDK

**Python:** `starlette.py`, `quart.py`, `litestar.py` (фабрика `make_litestar_middleware()` для Litestar 2).  
**JavaScript:** `integrations/fastify.js`; фронт: `integrations/react.js`, `integrations/vue.js`.

Исправлены пути `require` в `express.js` и `browser.js` (теперь `../index`).
