"""
Демо FastAPI + middleware SDK. Коллектор — отдельно на :8000, это приложение — :8010.
GET /boom — искусственная ошибка (уйдёт в мониторинг при capture_errors).

Запуск:
  pip install -r requirements.txt   # editable SDK из ../../../project/sdk-python
  python 02_fastapi_demo.py
  или: uvicorn 02_fastapi_demo:app --host 127.0.0.1 --port 8010
"""
from __future__ import annotations

import os

from fastapi import FastAPI

from demo_init import init_monitor
from error_monitor_sdk.integrations.fastapi import enable_fastapi_integration

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f")
API_KEY = os.environ.get("MONITOR_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4")

init_monitor(
    endpoint=ENDPOINT,
    project_id=PROJECT_ID,
    context={"demo": "fastapi"},
    api_key=API_KEY,
)

app = FastAPI(title="SDK FastAPI demo")

enable_fastapi_integration(
    app,
    user_id_func=lambda request: request.headers.get("X-User-ID", "anonymous"),
    capture_requests=True,
    capture_errors=True,
    exclude_paths=["/health"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/ok")
async def ok():
    return {"message": "ok"}


@app.get("/boom")
async def boom():
    raise InvalidRequestError("тестовая ошибка FastAPI для SDK")


@app.get("/error")
async def error():
    raise Exception("тестовая ошибка FastAPI для SDK")

@app.get("/error2")
async def error():
    raise Exception("тестовая ошибка FastAPI для SDK")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000)
