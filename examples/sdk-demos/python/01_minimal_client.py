"""
Событие без веб-фреймворка: init_monitor + track_event.
Запуск: python 01_minimal_client.py
"""
from __future__ import annotations

import os
import time

from demo_init import init_monitor
from error_monitor_sdk import track_event

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f")
API_KEY = os.environ.get("MONITOR_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4")


def main() -> None:
    init_monitor(
        endpoint=ENDPOINT,
        project_id=PROJECT_ID,
        context={"demo": "minimal_client"},
        api_key=API_KEY,
    )
    track_event(
        "sdk_manual_test",
        metadata={"note": "минимальный клиент без фреймворка"},
        page_url="https://example.com/sdk-demo",
    )
    print("Событие отправлено (фоновый поток). Ждём 2 с…")
    time.sleep(2)
    print("Готово. Проверьте таблицу events и очередь Celery.")


if __name__ == "__main__":
    main()
