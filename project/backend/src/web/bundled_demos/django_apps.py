import os

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self) -> None:
        from demo_init import init_monitor

        endpoint = 'http://127.0.0.1:8000'
        project_id = os.environ.get("MONITOR_PROJECT_ID", "3834e217-7416-46c3-a1e0-c47ce9b8642f")
        raw = os.environ.get("MONITOR_API_KEY", "FjEbQ-Tfj9LLBRGDyaJRwO3tI4YV0fOToOxOyiKCoG4")
        api_key = raw.strip() if raw else None

        init_monitor(
            endpoint=endpoint,
            project_id=project_id,
            context={'demo': 'django_mvp'},
            api_key=api_key,
        )
