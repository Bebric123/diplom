"""
Quart (async Flask). Порт :8013.
Запуск: python 05_quart_demo.py
"""
from __future__ import annotations

import os

from quart import Quart

from demo_init import init_monitor
from error_monitor_sdk.integrations.quart import enable_quart_integration

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f")
API_KEY = os.environ.get("MONITOR_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4")

init_monitor(
    endpoint=ENDPOINT,
    project_id=PROJECT_ID,
    context={"demo": "quart"},
    api_key=API_KEY,
)

app = Quart(__name__)
enable_quart_integration(app, user_id_func=lambda: "quart-demo-user")


@app.route("/")
async def index():
    return {"message": "ok"}


@app.route("/boom")
async def boom():
    raise RuntimeError("тестовая ошибка Quart для SDK")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8013)
