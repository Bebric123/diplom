# error_monitor_sdk/integrations/fastapi.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import traceback
import time
from typing import Optional, Callable, Dict, Any
import logging
import asyncio 

from ..client import _client
from ..utils.context import get_request_context

logger = logging.getLogger("error_monitor_sdk")

class FastAPIMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического мониторинга FastAPI приложений
    """
    
    def __init__(
        self,
        app: ASGIApp,
        user_id_func: Optional[Callable] = None,
        capture_requests: bool = True,
        capture_errors: bool = True,
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.user_id_func = user_id_func
        self.capture_requests = capture_requests
        self.capture_errors = capture_errors
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]
        
    async def dispatch(self, request: Request, call_next):
        # Проверяем, нужно ли исключить путь
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        
        # Получаем user_id
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
            # Выполняем запрос
            response = await call_next(request)
            
            # Логируем успешный запрос (если включено)
            if self.capture_requests and _client:
                duration = (time.time() - start_time) * 1000  # в миллисекундах
                
                metadata = {
                    "user_id": user_id,
                    "status_code": response.status_code,
                    "duration_ms": duration,
                    "response_size": response.headers.get("content-length"),
                    **get_request_context(request, "fastapi")
                }
                
                _client.send_event(
                    action=f"http: {request.method} {request.url.path}",
                    metadata=metadata,
                    page_url=str(request.url)
                )
            
            return response
            
        except Exception as e:
            # Логируем ошибку
            if self.capture_errors and _client:
                duration = (time.time() - start_time) * 1000
                
                error_metadata = {
                    "user_id": user_id,
                    "duration_ms": duration,
                    "exception_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                    **get_request_context(request, "fastapi")
                }
                
                _client.capture_exception(
                    exception=e,
                    metadata=error_metadata,
                    page_url=str(request.url)
                )
            
            # Возвращаем ошибку клиенту
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

def enable_fastapi_integration(
    app: FastAPI,
    user_id_func: Optional[Callable] = None,
    capture_requests: bool = True,
    capture_errors: bool = True,
    exclude_paths: Optional[list] = None
):
    """
    Подключает мониторинг к FastAPI приложению
    
    Args:
        app: FastAPI приложение
        user_id_func: Функция для получения user_id из request
        capture_requests: Логировать все запросы
        capture_errors: Перехватывать ошибки
        exclude_paths: Пути, которые не нужно мониторить
    
    Example:
        >>> from fastapi import FastAPI
        >>> from error_monitor_sdk import init_monitor
        >>> from error_monitor_sdk.integrations.fastapi import enable_fastapi_integration
        >>>
        >>> init_monitor("http://localhost:8000", project_id="my-fastapi-app")
        >>>
        >>> app = FastAPI()
        >>> enable_fastapi_integration(
        ...     app,
        ...     user_id_func=lambda request: request.headers.get("X-User-ID", "anonymous"),
        ...     exclude_paths=["/health"]
        ... )
    """
    if _client is None:
        logger.warning("⚠️ ErrorMonitor SDK not initialized. Call init_monitor() first.")
        return
    
    # Добавляем middleware
    app.add_middleware(
        FastAPIMonitoringMiddleware,
        user_id_func=user_id_func,
        capture_requests=capture_requests,
        capture_errors=capture_errors,
        exclude_paths=exclude_paths
    )
    
    # Добавляем обработчик исключений
    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        if capture_errors and _client:
            user_id = "anonymous"
            if user_id_func:
                try:
                    if asyncio.iscoroutinefunction(user_id_func):
                        user_id = await user_id_func(request)
                    else:
                        user_id = user_id_func(request)
                except Exception:
                    pass
            
            _client.capture_exception(
                exception=exc,
                metadata={
                    "user_id": user_id,
                    "exception_type": type(exc).__name__,
                    **get_request_context(request, "fastapi")
                },
                page_url=str(request.url)
            )
        
        # Пробрасываем дальше
        raise exc
    
    logger.info("✅ FastAPI integration enabled")