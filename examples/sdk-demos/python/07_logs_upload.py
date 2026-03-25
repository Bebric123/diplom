"""
Отправка хвоста лог-файла на POST /logs/upload (send_log_file).
Запуск: python 07_logs_upload.py
"""
from __future__ import annotations

import os
import tempfile
import time

from error_monitor_sdk import init_monitor
from error_monitor_sdk.logs import send_log_file

ENDPOINT = os.environ.get("MONITOR_URL", "http://127.0.0.1:8000")
PROJECT_ID = os.environ.get("MONITOR_PROJECT_ID", "00000000-0000-4000-8000-000000000001")


def main() -> None:
    init_monitor(
        endpoint=ENDPOINT,
        project_id=PROJECT_ID,
        context={"environment": "sdk-demo-logs"},
    )
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as tmp:
        tmp.write("2025-01-01 info: started\n")
        tmp.write("2025-01-01 ERROR simulated failure for SDK test\n")
        tmp.write("2025-01-01 WARN something odd\n")
        path = tmp.name

    ok = send_log_file(path, lines=10, service_name="sdk-demo", environment="demo")
    print("send_log_file queued:", ok)
    time.sleep(3)
    print("Проверьте log_files и задачу process_log_file в Celery.")


if __name__ == "__main__":
    main()
