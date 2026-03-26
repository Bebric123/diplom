"""
Litestar + middleware из SDK. Порт :8014.
Запуск: litestar run 06_litestar_demo:app --host 127.0.0.1 --port 8014
  (или: uvicorn 06_litestar_demo:app --host 127.0.0.1 --port 8014)
"""
from __future__ import annotations

import os

from litestar import Litestar, get

from error_monitor_sdk import init_monitor
from error_monitor_sdk.integrations.litestar import make_litestar_middleware

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "00000000-0000-4000-8000-000000000001")
API_KEY = os.environ.get("MONITOR_API_KEY") or None

init_monitor(
    endpoint=ENDPOINT,
    project_id=PROJECT_ID,
    context={"demo": "litestar"},
    api_key=API_KEY,
)


@get("/health")
async def health() -> dict:
    return {"ok": True}


@get("/")
async def index() -> str:
    return "ok"


@get("/boom")
async def boom():
    raise RuntimeError("тестовая ошибка Litestar для SDK")


app = Litestar(
    route_handlers=[health, index, boom],
    middleware=[
        make_litestar_middleware(
            user_id_func=lambda request: request.headers.get("X-User-ID", "anonymous"),
            capture_requests=False,
            capture_errors=True,
            exclude_paths=["/health"],
        )
    ],
)
