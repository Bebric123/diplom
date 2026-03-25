"""
Интеграция для Quart (async Flask-подобный фреймворк).
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import traceback
from typing import Any, Callable, Optional

from quart import request

from ..client import get_client

logger = logging.getLogger("error_monitor_sdk")


def enable_quart_integration(app: Any, user_id_func: Optional[Callable[..., Any]] = None) -> None:
    if get_client() is None:
        logger.warning("ErrorMonitor SDK not initialized. Call init_monitor() first.")
        return

    @app.errorhandler(Exception)
    async def handle_exception(exc: BaseException) -> None:
        client = get_client()
        if client is None:
            raise exc

        user_id = "anonymous"
        if user_id_func:
            try:
                uid = user_id_func()
                if asyncio.iscoroutine(uid):
                    user_id = await uid
                else:
                    user_id = uid
            except Exception:
                pass

        page_url = "N/A"
        method = "GET"
        path = "/"
        user_agent = ""
        try:
            if request:
                page_url = request.url
                method = request.method
                path = request.path
                user_agent = request.headers.get("User-Agent", "")
        except Exception:
            pass

        event_data = {
            "project_id": client.project_id or "default-project",
            "action": f"quart_exception: {type(exc).__name__}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "context": {
                "platform": "backend",
                "language": "python",
                "os_family": client.context.get("os_family", "Linux") if getattr(client, "context", None) else "Linux",
                "browser_family": "server",
            },
            "meta": {
                "url": page_url,
                "method": method,
                "path": path,
                "user_agent": user_agent,
                "user_id": user_id,
                "exception_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            },
        }

        if getattr(client, "context", None):
            for key, value in client.context.items():
                if key not in event_data["meta"] and key not in ("platform", "language", "os_family"):
                    event_data["meta"][f"custom_{key}"] = value

        try:
            client._send_sync(event_data)
        except Exception as send_err:
            logger.error("Failed to send error event: %s", send_err)

        raise exc

    logger.info("Quart integration enabled")
