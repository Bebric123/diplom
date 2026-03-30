"""
Нагрузочный сценарий для коллектора (Locust).

Запуск (из каталога project/backend, коллектор уже поднят):

  pip install -r requirements/dev.txt
  set MONITOR_HOST=http://127.0.0.1:8000
  set LOADTEST_PROJECT_ID=<uuid существующего проекта>
  set LOADTEST_API_KEY=<ключ, если COLLECTOR_REQUIRE_API_KEY=true>
  locust -f tests/load/locustfile.py

Веб-UI: http://localhost:8089
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CollectorIngestUser(HttpUser):
    host = os.environ.get("MONITOR_HOST", "http://127.0.0.1:8000")
    wait_time = between(0.05, 0.3)

    def on_start(self):
        self.project_id = os.environ.get("LOADTEST_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f").strip()
        self.api_key = os.environ.get("LOADTEST_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4").strip()
        if not self.project_id:
            self.project_id = str(uuid.uuid4())

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-Api-Key"] = self.api_key
        return h

    @task(3)
    def health(self):
        self.client.get("/health", name="/health")

    @task(10)
    def track_minimal(self):
        self.client.post(
            "/track",
            json={
                "project_id": self.project_id,
                "action": "loadtest_event",
                "timestamp": _ts(),
                "context": {"platform": "loadtest"},
                "meta": {"source": "locust"},
            },
            headers=self._headers(),
            name="/track",
        )

    @task(2)
    def track_with_error(self):
        self.client.post(
            "/track",
            json={
                "project_id": self.project_id,
                "action": "loadtest_error",
                "timestamp": _ts(),
                "context": {"platform": "loadtest"},
                "meta": {
                    "error_message": "simulated failure",
                    "error_stack": "File \"x.py\", line 1\n  raise RuntimeError()",
                },
            },
            headers=self._headers(),
            name="/track (error meta)",
        )

    @task(1)
    def logs_upload_small(self):
        self.client.post(
            "/logs/upload",
            json={
                "project_id": self.project_id,
                "filename": "loadtest.log",
                "content": "ERROR timeout\nWARN slow query\n",
                "lines_sent": 2,
                "total_lines": 1000,
            },
            headers=self._headers(),
            name="/logs/upload",
        )
