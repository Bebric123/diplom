# Фронтенд-демо (проверка SDK в браузере)

Репозиторий: `git clone https://github.com/Bebric123/diplom.git` — SDK лежит в `project/sdk-js`, эти демо в `examples/sdk-demos/frontend/`.

Здесь **Vite** + **React** или **Vue 3**: подключается локальный пакет `error-monitor-sdk` (`project/sdk-js`), `initMonitor`, `enableBrowserIntegration`, Error Boundary / Vue `errorHandler`.

## Зачем отдельный каталог

Сборка `sdk-js` рассчитана на Node (`require('os')`, `setImmediate`, `process.version`). В каждом демо есть **shim** и настройки Vite — без этого бандл не соберётся.

Пакет SDK в формате **CommonJS**: в Vite удобнее писать `import * as MonitorSdk from 'error-monitor-sdk'` и вызывать `MonitorSdk.initMonitor`, `MonitorSdk.trackEvent`, а интеграции — `import * as ReactMonitor from 'error-monitor-sdk/integrations/react'` и далее `ReactMonitor.MonitorErrorBoundary`.

## Переменные (`.env` в каталоге демо)

Создайте `.env` по образцу `.env.example` (сам `.env` в git не кладётся — см. `.gitignore` в каталоге демо). Префикс **`VITE_`** обязателен — иначе Vite не отдаст значения в браузер.

```env
VITE_MONITOR_URL=http://127.0.0.1:8000
VITE_MONITOR_PROJECT_ID=ваш-uuid
VITE_MONITOR_API_KEY=ваш-ключ
```

**CORS:** коллектор должен разрешать origin дев-сервера Vite (например `http://127.0.0.1:5173`). В `.env` бэкенда задайте `CORS_ALLOW_ORIGINS=http://127.0.0.1:5173` или `*` для локальных тестов.

**Ключ в браузере** — только для демо; в проде лучше прокси на своём бэкенде.

## Почему в Telegram ничего нет, хотя в консоли 200

Цепочка такая: браузер → `POST /track` → событие в **PostgreSQL** → асинхронно **Celery** (`process_event`: классификация, группа, отправка в Telegram).

Нужны **все** из списка:

- запущен **Celery worker** и **Redis** (в Docker — сервисы `worker` + `redis`, либо локально `celery -A src.workers.celery_app worker …`);
- у проекта в БД указан **Telegram chat id** (регистрация `http://127.0.0.1:8000/register` или `projects.telegram_chat_id`);
- `TELEGRAM_BOT_TOKEN` в окружении воркера/бота корректен.

Пока воркер не обработал задачу, в чате тишина — это не баг демо.

## «Белый экран»

1. **F12 → Console** — красные ошибки (import SDK, CORS, неверный `projectId`).
2. В корне **обязателен** `VITE_MONITOR_PROJECT_ID` в `.env`; без него в интерфейсе показано сообщение, а кнопки демо скрыты.
3. **Перезапустите** `npm run dev` после любого изменения `.env` (Vite кэширует env на старте).
4. **CORS** на коллекторе: origin дев-сервера (например `http://127.0.0.1:5173`).

## Запуск

### React

```bash
cd examples/sdk-demos/frontend/react-vite
npm install
npm run dev
```

Откройте URL из консоли Vite, нажмите кнопки «ошибка в Boundary» / «глобальная ошибка» / «track».

### Vue 3

```bash
cd examples/sdk-demos/frontend/vue-vite
npm install
npm run dev
```

## Angular

Готового пакета в `sdk-js` нет. Имеет смысл завести отдельный проект `ng new`, добавить тот же path на `sdk-js`, в `main.ts` после `initMonitor` зарегистрировать `ErrorHandler` с вызовом `getClient().captureException` — по аналогии с Vue/React (см. общий README `examples/sdk-demos`).
