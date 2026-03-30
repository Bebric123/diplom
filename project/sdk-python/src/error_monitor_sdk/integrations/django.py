# error_monitor_sdk/integrations/django.py
import traceback
import time
import logging
from typing import Optional, Callable

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from ..client import get_client
from ..utils.context import get_request_context

logger = logging.getLogger("error_monitor_sdk")

class DjangoMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware для автоматического мониторинга Django приложений
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.user_id_func = None
        self.capture_requests = True
        self.capture_errors = True
        # /track и /logs/upload: если MONITOR_URL случайно указывает на этот же Django,
        # исходящий POST от SDK снова проходит middleware → send_event → рекурсия и 404.
        self.exclude_paths = [
            "/admin/jsi18n/",
            "/favicon.ico",
            "/health/",
            "/track",
            "/track/",
            "/logs/upload",
            "/logs/upload/",
        ]
        
    def configure(self, user_id_func=None, capture_requests=True, capture_errors=True, exclude_paths=None):
        """Настройка middleware"""
        self.user_id_func = user_id_func
        self.capture_requests = capture_requests
        self.capture_errors = capture_errors
        if exclude_paths:
            self.exclude_paths.extend(exclude_paths)
        return self
    
    def process_request(self, request: WSGIRequest):
        """Начало обработки запроса"""
        # Проверяем, нужно ли исключить путь
        if request.path in self.exclude_paths:
            return None
        
        # Сохраняем время начала
        request.monitor_start_time = time.time()
        
        # Получаем user_id
        request.monitor_user_id = "anonymous"
        if self.user_id_func:
            try:
                request.monitor_user_id = self.user_id_func(request)
            except Exception:
                pass
        
        return None
    
    def process_response(self, request: WSGIRequest, response: HttpResponse):
        """Завершение обработки запроса"""
        if not hasattr(request, 'monitor_start_time'):
            return response
        
        client = get_client()
        if not client:
            return response

        duration = (time.time() - request.monitor_start_time) * 1000

        metadata = {
            "user_id": getattr(request, 'monitor_user_id', 'anonymous'),
            "status_code": response.status_code,
            "duration_ms": duration,
            "response_size": len(response.content) if hasattr(response, 'content') else None,
            **get_request_context(request, "django")
        }
        
        # Добавляем информацию о пользователе Django (если есть)
        if hasattr(request, 'user') and request.user.is_authenticated:
            metadata["django_user_id"] = request.user.id
            metadata["django_username"] = request.user.username
        
        # Отправляем событие
        if self.capture_requests:
            client.send_event(
                action=f"http: {request.method} {request.path}",
                metadata=metadata,
                page_url=request.build_absolute_uri(),
            )
        
        return response
    
    def process_exception(self, request: WSGIRequest, exception: Exception):
        """Обработка исключения"""
        if not hasattr(request, 'monitor_start_time'):
            return None
        
        client = get_client()
        if not client or not self.capture_errors:
            return None

        duration = (time.time() - request.monitor_start_time) * 1000

        error_metadata = {
            "user_id": getattr(request, 'monitor_user_id', 'anonymous'),
            "duration_ms": duration,
            "exception_type": type(exception).__name__,
            "error_message": str(exception),
            "traceback": traceback.format_exc(),
            **get_request_context(request, "django")
        }
        
        client.capture_exception(
            exception=exception,
            metadata=error_metadata,
            page_url=request.build_absolute_uri(),
        )
        
        return None


def enable_django_integration(
    user_id_func: Optional[Callable] = None,
    capture_requests: bool = True,
    capture_errors: bool = True,
    exclude_paths: Optional[list] = None
):
    """
    Подключает мониторинг к Django приложению
    
    Args:
        user_id_func: Функция для получения user_id из request
        capture_requests: Логировать все запросы
        capture_errors: Перехватывать ошибки
        exclude_paths: Пути, которые не нужно мониторить
    
    Returns:
        DjangoMonitoringMiddleware: Настроенный middleware
    
    Example:
        # В settings.py
        >>> from error_monitor_sdk import init_monitor
        >>> from error_monitor_sdk.integrations.django import enable_django_integration
        >>>
        >>> init_monitor("http://localhost:8000", project_id="my-django-app")
        >>>
        >>> MIDDLEWARE = [
        ...     'django.middleware.security.SecurityMiddleware',
        ...     enable_django_integration(
        ...         user_id_func=lambda request: request.user.id if request.user.is_authenticated else "anonymous",
        ...         exclude_paths=["/admin/"]
        ...     ),
        ...     'django.contrib.sessions.middleware.SessionMiddleware',
        ...     # ... остальные middleware
        ... ]
    """
    if get_client() is None:
        logger.warning("⚠️ ErrorMonitor SDK not initialized. Call init_monitor() first.")
        return "django.middleware.common.CommonMiddleware"  # Заглушка
    
    middleware = DjangoMonitoringMiddleware()
    middleware.configure(
        user_id_func=user_id_func,
        capture_requests=capture_requests,
        capture_errors=capture_errors,
        exclude_paths=exclude_paths
    )
    
    logger.info("✅ Django integration enabled")
    return middleware