"""
Интеграция для Starlette (и любых ASGI-приложений на его основе).
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Any, Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from ..client import get_client
from ..utils.context import get_request_context

logger = logging.getLogger("error_monitor_sdk")


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware: опционально логирует запросы и отправляет необработанные ошибки в коллектор."""

    def __init__(
        self,
        app: ASGIApp,
        user_id_func: Optional[Callable[..., Any]] = None,
        capture_requests: bool = True,
        capture_errors: bool = True,
        exclude_paths: Optional[list] = None,
    ):
        super().__init__(app)
        self.user_id_func = user_id_func
        self.capture_requests = capture_requests
        self.capture_errors = capture_errors
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        start_time = time.time()
        user_id = "anonymous"
        if self.user_id_func:
            try:
                if asyncio.iscoroutinefunction(self.user_id_func):
                    user_id = await self.user_id_func(request)
                else:
                    user_id = self.user_id_func(request)
            except Exception:
                pass

        try:
            response = await call_next(request)
            client = get_client()
            if self.capture_requests and client:
                duration_ms = (time.time() - start_time) * 1000
                metadata = {
                    "user_id": user_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "response_size": response.headers.get("content-length"),
                    **get_request_context(request, "starlette"),
                }
                client.send_event(
                    action=f"http: {request.method} {request.url.path}",
                    metadata=metadata,
                    page_url=str(request.url),
                )
            return response
        except Exception as e:
            client = get_client()
            if self.capture_errors and client:
                duration_ms = (time.time() - start_time) * 1000
                error_metadata = {
                    "user_id": user_id,
                    "duration_ms": duration_ms,
                    "exception_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                    **get_request_context(request, "starlette"),
                }
                client.capture_exception(
                    exception=e,
                    metadata=error_metadata,
                    page_url=str(request.url),
                )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


def enable_starlette_integration(
    app: Any,
    user_id_func: Optional[Callable[..., Any]] = None,
    capture_requests: bool = True,
    capture_errors: bool = True,
    exclude_paths: Optional[list] = None,
) -> None:
    if get_client() is None:
        logger.warning("ErrorMonitor SDK not initialized. Call init_monitor() first.")
        return
    app.add_middleware(
        MonitoringMiddleware,
        user_id_func=user_id_func,
        capture_requests=capture_requests,
        capture_errors=capture_errors,
        exclude_paths=exclude_paths,
    )
    logger.info("Starlette / ASGI monitoring middleware enabled")
