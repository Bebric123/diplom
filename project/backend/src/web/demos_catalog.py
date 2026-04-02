"""Метаданные и загрузка текстов демо для страницы /docs/demos."""
from __future__ import annotations

from pathlib import Path

_BASE = Path(__file__).resolve().parent / "bundled_demos"

# Кортеж: (имя_файла, title_ru, title_en) или (имя, title_ru, title_en, lang_override)
_SECTIONS: list[dict] = [
    {
        "title_ru": "Обзор и зависимости",
        "title_en": "Overview & dependencies",
        "hint_ru": "Описание каталога examples/sdk-demos в репозитории и файлы requirements / package.",
        "hint_en": "examples/sdk-demos layout and dependency manifests.",
        "items": [
            ("sdk_demos_README.md", "README демо-репозитория", "Demos README", "markdown"),
            ("python_requirements_demo.txt", "Python: requirements для демо", "Python: demo requirements.txt", "text"),
            ("package_nodejs_demo.json", "Node.js: package.json демо", "Node.js: demo package.json", "json"),
            ("php_composer_demoroot.json", "PHP: composer.json (корень php-демо)", "PHP: demo composer.json", "json"),
            ("frontend_README.md", "Фронтенд: README React/Vue", "Frontend React/Vue README", "markdown"),
        ],
    },
    {
        "title_ru": "Python",
        "title_en": "Python",
        "hint_ru": "Запуск из examples/sdk-demos/python: рядом должен быть установлен SDK (pip install -e ../../project/sdk-python или из клона). Переменные MONITOR_URL, MONITOR_PROJECT_ID, MONITOR_API_KEY.",
        "hint_en": "Run from examples/sdk-demos/python with SDK installed. Env: MONITOR_URL, MONITOR_PROJECT_ID, MONITOR_API_KEY.",
        "items": [
            ("demo_init.py", "Общий init_monitor", "Shared init_monitor"),
            ("01_minimal_client.py", "Минимальный клиент", "Minimal client"),
            ("02_fastapi_demo.py", "FastAPI + middleware", "FastAPI + middleware"),
            ("03_flask_demo.py", "Flask", "Flask"),
            ("04_starlette_demo.py", "Starlette", "Starlette"),
            ("05_quart_demo.py", "Quart", "Quart"),
            ("06_litestar_demo.py", "Litestar", "Litestar"),
            ("07_logs_upload.py", "Загрузка логов", "Log upload"),
        ],
    },
    {
        "title_ru": "Python — Django (MVP)",
        "title_en": "Python — Django (MVP)",
        "hint_ru": "Мини-проект django_mvp в examples/sdk-demos/python/django_mvp — фрагменты для просмотра интеграции.",
        "hint_en": "django_mvp under examples/sdk-demos/python/django_mvp.",
        "items": [
            ("django_manage.py", "manage.py", "manage.py"),
            ("django_settings.py", "settings.py", "settings.py"),
            ("django_urls.py", "urls.py", "urls.py"),
            ("django_apps.py", "monitoring/apps.py", "monitoring/apps.py"),
            ("django_views.py", "monitoring/views.py", "monitoring/views.py"),
        ],
    },
    {
        "title_ru": "Node.js",
        "title_en": "Node.js",
        "hint_ru": "examples/sdk-demos/nodejs — запуск: node 01_minimal.cjs (пакет error-monitor-sdk из project/sdk-js).",
        "hint_en": "examples/sdk-demos/nodejs; run e.g. node 01_minimal.cjs.",
        "items": [
            ("01_minimal.cjs", "Минимальный скрипт", "Minimal script"),
            ("02_express_demo.cjs", "Express", "Express"),
            ("03_fastify_demo.cjs", "Fastify", "Fastify"),
            ("04_upload_log.cjs", "Загрузка лога", "Log upload"),
        ],
    },
    {
        "title_ru": "PHP",
        "title_en": "PHP",
        "hint_ru": "examples/sdk-demos/php — composer и автозагрузка к sdk-php.",
        "hint_en": "examples/sdk-demos/php.",
        "items": [
            ("01_minimal.php", "Минимальный клиент", "Minimal client"),
            ("02_builtin_server.php", "Встроенный сервер", "Built-in server"),
            ("03_slim_demo.php", "Slim", "Slim"),
            ("04_upload_log.php", "Загрузка лога", "Log upload"),
            ("laravel_providers_snippet.php", "Laravel: фрагмент providers", "Laravel: providers snippet"),
            ("laravel_report_exception_partial.php", "Laravel: reportable exception", "Laravel: reportable exception"),
            ("laravel_demo_README.md", "Laravel demo README", "Laravel demo README", "markdown"),
        ],
    },
    {
        "title_ru": "React (Vite)",
        "title_en": "React (Vite)",
        "hint_ru": "examples/sdk-demos/frontend/react-vite — npm install, переменные в .env (см. .env.example в демо).",
        "hint_en": "examples/sdk-demos/frontend/react-vite.",
        "items": [
            ("react_package.json", "package.json", "package.json", "json"),
            ("react_index.html", "index.html", "index.html", "html"),
            ("react_vite.config.js", "vite.config.js", "vite.config.js", "javascript"),
            ("react_main.jsx", "src/main.jsx", "src/main.jsx", "javascript"),
            ("react_App.jsx", "src/App.jsx", "src/App.jsx", "javascript"),
            ("react_setupMonitorEnv.js", "src/setupMonitorEnv.js", "src/setupMonitorEnv.js", "javascript"),
        ],
    },
    {
        "title_ru": "Vue (Vite)",
        "title_en": "Vue (Vite)",
        "hint_ru": "examples/sdk-demos/frontend/vue-vite.",
        "hint_en": "examples/sdk-demos/frontend/vue-vite.",
        "items": [
            ("vue_package.json", "package.json", "package.json", "json"),
            ("vue_index.html", "index.html", "index.html", "html"),
            ("vue_vite.config.js", "vite.config.js", "vite.config.js", "javascript"),
            ("vue_main.js", "src/main.js", "src/main.js", "javascript"),
            ("vue_App.vue", "src/App.vue", "src/App.vue", "html"),
            ("vue_setupMonitorEnv.js", "src/setupMonitorEnv.js", "src/setupMonitorEnv.js", "javascript"),
        ],
    },
    {
        "title_ru": "Браузер",
        "title_en": "Browser",
        "hint_ru": "Нужен CORS на коллекторе; страницу открывать через HTTP-сервер, не file://.",
        "hint_en": "Enable CORS; serve over HTTP, not file://.",
        "items": [
            ("fetch_track_demo.html", "fetch → POST /track", "fetch → POST /track"),
        ],
    },
]


def _lang_for_file(fname: str, override: str | None) -> str:
    if override:
        return override
    low = fname.lower()
    if low.endswith(".html") or low.endswith(".vue"):
        return "html"
    if low.endswith(".json"):
        return "json"
    if low.endswith(".md"):
        return "markdown"
    if low.endswith(".php"):
        return "php"
    if low.endswith((".js", ".jsx", ".cjs", ".mjs")):
        return "javascript"
    return "python"


def load_demo_sections() -> list[dict]:
    out: list[dict] = []
    for sec in _SECTIONS:
        items_out: list[dict] = []
        for tup in sec["items"]:
            if len(tup) == 4:
                fname, title_ru, title_en, lang_o = tup
            else:
                fname, title_ru, title_en = tup
                lang_o = None
            path = _BASE / fname
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                source = f"# файл не найден в образе: {fname}\n"
            lang = _lang_for_file(fname, lang_o)
            safe_id = (
                fname.replace(".", "_")
                .replace("/", "_")
                .replace("\\", "_")
                .replace(" ", "_")
            )
            items_out.append(
                {
                    "id": safe_id,
                    "file": fname,
                    "title_ru": title_ru,
                    "title_en": title_en,
                    "lang": lang,
                    "source": source,
                }
            )
        out.append(
            {
                "title_ru": sec["title_ru"],
                "title_en": sec["title_en"],
                "hint_ru": sec.get("hint_ru", ""),
                "hint_en": sec.get("hint_en", ""),
                "items": items_out,
            }
        )
    return out


def flat_demo_index() -> list[dict]:
    """Плоский список для API/отладки."""
    rows: list[dict] = []
    for sec in load_demo_sections():
        for it in sec["items"]:
            rows.append({**it, "section_ru": sec["title_ru"], "section_en": sec["title_en"]})
    return rows
