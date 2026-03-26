"""
Событие без веб-фреймворка: init_monitor + track_event.
Запуск: python 01_minimal_client.py
"""
from __future__ import annotations

import os
import time

from error_monitor_sdk import init_monitor, track_event

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "00000000-0000-4000-8000-000000000001")
API_KEY = os.environ.get("MONITOR_API_KEY") or None


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
