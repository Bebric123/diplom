# Демо и ручная проверка SDK

Коллектор (FastAPI) по умолчанию: `http://127.0.0.1:8000`. Запустите стек (`docker-compose` в `project/docker`) и один раз выполните `sql/seed_demo_project.sql` в базе, чтобы существовал проект с UUID по умолчанию.

Переменные окружения (опционально):

- `MONITOR_URL` — URL коллектора (по умолчанию `http://127.0.0.1:8000`)
- `MONITOR_PROJECT_ID` — UUID проекта (по умолчанию `00000000-0000-4000-8000-000000000001`)

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
