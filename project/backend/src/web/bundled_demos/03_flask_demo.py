"""
Flask + errorhandler SDK. Порт :8011.
Запуск: python 03_flask_demo.py
Проверка: curl http://127.0.0.1:8011/boom
"""
from __future__ import annotations

import os

from flask import Flask

from demo_init import init_monitor
from error_monitor_sdk.integrations.flask import enable_flask_integration

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f")
API_KEY = os.environ.get("MONITOR_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4")

init_monitor(
    endpoint=ENDPOINT,
    project_id=PROJECT_ID,
    context={"demo": "flask"},
    api_key=API_KEY,
)

app = Flask(__name__)
enable_flask_integration(app, user_id_func=lambda: "flask-demo-user")


@app.route("/")
def index():
    return {"message": "ok"}


@app.route("/boom")
def boom():
    raise ValueError("тестовая ошибка Flask для SDK")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8011, debug=False)
