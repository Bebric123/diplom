"""
Фабрика middleware для Litestar 2 (список `middleware` принимает callable ``(app) -> ASGIApp``).

Пример::

    from litestar import Litestar, get
    from error_monitor_sdk.integrations.litestar import make_litestar_middleware

    @get("/")
    async def hello() -> str:
        return "ok"

    app = Litestar(
        route_handlers=[hello],
        middleware=[make_litestar_middleware(capture_requests=False)],
    )
"""
from __future__ import annotations

from typing import Any, Callable

from .starlette import MonitoringMiddleware


def make_litestar_middleware(**kwargs: Any) -> Callable[[Any], Any]:
    """Возвращает фабрику для ``Litestar(..., middleware=[...])``."""
    try:
        from litestar.types import ASGIApp
    except ImportError as e:  # pragma: no cover
        raise ImportError("Установите пакет litestar для этой интеграции") from e

    def middleware_factory(app: ASGIApp) -> ASGIApp:
        return MonitoringMiddleware(app, **kwargs)

    return middleware_factory
