"""
Чистый Starlette (без FastAPI). Порт :8012.
Запуск: uvicorn 04_starlette_demo:app --host 127.0.0.1 --port 8012
"""
from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from error_monitor_sdk import init_monitor
from error_monitor_sdk.integrations.starlette import enable_starlette_integration

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "00000000-0000-4000-8000-000000000001")

init_monitor(endpoint=ENDPOINT, project_id=PROJECT_ID, context={"demo": "starlette"})


async def home(_: Request):
    return PlainTextResponse("ok")


async def boom(_: Request):
    raise RuntimeError("тестовая ошибка Starlette для SDK")


def health(_: Request):
    return JSONResponse({"ok": True})


routes = [
    Route("/health", health),
    Route("/", home),
    Route("/boom", boom),
]

app = Starlette(routes=routes)

enable_starlette_integration(
    app,
    user_id_func=lambda request: request.headers.get("X-User-ID", "anonymous"),
    capture_requests=False,
    capture_errors=True,
    exclude_paths=["/health"],
)
