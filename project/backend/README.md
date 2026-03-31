# Backend (коллектор Error Monitor)

FastAPI-сервис приёма событий и логов, регистрация проектов, отчёты и Telegram-бот.

## Требования

- Python 3.11+ (как в Docker-образе)
- PostgreSQL 15+
- Redis (для Celery)

## Установка из клона репозитория

Из корня монорепозитория:

```bash
cd project/backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

Переменные окружения: см. использование в `src/core/config.py` и шаблон `project/docker/.env`. Минимум для локального запуска без Docker — строка подключения к PostgreSQL и при необходимости `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, `COLLECTOR_REQUIRE_API_KEY`, `API_KEY_PEPPER`.

## Миграции

```bash
cd project/backend
alembic upgrade head
```

## Запуск API

```bash
cd project/backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Страницы: `/` — лендинг, `/register` — создание проекта, `/docs/sdk` — инструкции по SDK, `/docs` — Swagger.

## Celery и бот

В отдельных терминалах (из `project/backend`, с тем же `.env` / переменными):

```bash
celery -A src.workers.celery_app.celery_app worker --loglevel=info
celery -A src.workers.celery_app.celery_app beat --loglevel=info
python -m src.services.telegram_bot
```

## Анализ ошибок для Telegram (только локальный GGUF)

Переменные окружения:

| Переменная | Значение |
|------------|----------|
| `ERROR_ANALYSIS_BACKEND` | `local_gguf` (по умолчанию) или `none` (заглушка без ИИ) |
| `LOCAL_LLM_GGUF_PATH` | **Обязательно** для ИИ: полный путь к файлу `.gguf` |
| `LOCAL_LLM_N_CTX` | Контекст (по умолчанию 8192) |
| `LOCAL_LLM_MAX_TOKENS` | Лимит ответа (по умолчанию 1024; для короткого JSON можно уменьшить) |
| `LOCAL_LLM_REPEAT_PENALTY` | Штраф повторов (по умолчанию 1.18; помогает против зацикливания на слабых квантах) |
| `LOCAL_LLM_JSON_GRAMMAR` | `true` (по умолчанию): ответ ограничен JSON-схемой (severity/criticality/recommendation) через llama.cpp grammar |
| `LOCAL_LLM_N_THREADS` | Потоки CPU, `0` = авто |
| `LOCAL_LLM_N_GPU_LAYERS` | Слои на GPU для llama.cpp (`0` = только CPU) |

**Скорость:** 4B «Thinking» на **CPU** (`n_gpu_layers=0`) часто даёт **десятки секунд — несколько минут** на один запрос — это нормально. Быстрее: **GPU** (`LOCAL_LLM_N_GPU_LAYERS` > 0 при CUDA), **меньше `LOCAL_LLM_MAX_TOKENS`** (если модель укладывается в JSON), **не-Thinking** instruct-модель, **`CELERY_WORKER_CONCURRENCY=1`**, чтобы не грузить CPU несколькими копиями модели.

Если модель всё равно «залипает» в повторяющийся текст вместо JSON (типично для **IQ1** и части Thinking-сборок), код после неудачных попыток подставляет **эвристическую** классификацию по тексту ошибки; для стабильного JSON лучше взять квант **Q4_K_M** (или выше) и **instruct без thinking**.

### Качество анализа: какую GGUF взять

Слабые кванты (**IQ1**, **IQ2**) и модели **Thinking** часто дают формальные уровни («незначительно» / «не критично») и пустые рекомендации даже при JSON-грамматике — для диплома/продакшена лучше заменить файл `.gguf`.

| Ориентир | Пример поиска на Hugging Face | Примечание |
|----------|-------------------------------|------------|
| **Хороший баланс** | `Qwen2.5-7B-Instruct-GGUF`, квант **Q4_K_M** или **Q5_K_M** | Заметно умнее 4B; на CPU дольше, на GPU — разумно |
| **Легче по ресурсам** | `Qwen2.5-3B-Instruct-GGUF` или **Qwen3-4B** вариант **Instruct** (не Thinking), **Q4_K_M** | Не брать `IQ1_M` / `UD-IQ*` для осмысленного текста |
| **Тяжелее и лучше** | `Qwen2.5-14B-Instruct-GGUF` **Q4_K_M** (или **Q5** при запасе VRAM) | Нужна видеокарта с достаточной памятью или терпение на CPU |

Ориентир по памяти (очень грубо): **Q4_K_M** у 7B ≈ **4–5 ГБ** VRAM при полном оффлоаде слоёв; на CPU хватает RAM под размер файла + накладные расходы. Путь к новому файлу — снова в `LOCAL_LLM_GGUF_PATH` (том `./models` в Docker).

Зависимость `llama-cpp-python` входит в `requirements/base.txt`. Репозитории `*-GGUF` на Hugging Face — файлы для llama.cpp; скачайте один квант (например Q4_K_M) и укажите путь в `LOCAL_LLM_GGUF_PATH` (том в Docker или путь на хосте).

## Тесты

```bash
cd project/backend
pytest tests/ -q
```

Часть интеграционных тестов пропускается без настроенной тестовой БД (`TEST_DATABASE_URL`).

## Поведение Telegram-бота

- **`/stats`**, **`/report`** — только в чате, чей id совпадает с `projects.telegram_chat_id` (тот же чат, куда уходят алерты). Статистика и Excel фильтруются по `project_id` этого проекта.
- **`/task`** с UUID — в группе доступна только задача того же проекта; в личке — поиск по всей базе (удобство отладки).
