import os
import json
import logging
import threading
import traceback
from typing import Optional, Dict, Any, Callable
import requests
from datetime import datetime

_logger = logging.getLogger("error_monitor_sdk")

class MonitorClient:
    def __init__(self, 
                 endpoint: str, 
                 user_id_func: Optional[Callable] = None, 
                 context: Optional[Dict] = None, 
                 project_id: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.endpoint = endpoint.rstrip("/")
        self.project_id = project_id or "default-project"
        self.user_id_func = user_id_func
        self.context = context or {}
        self.api_key = (api_key or "").strip() or None
        self.session = requests.Session()
        
        # Добавляем заголовки
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ErrorMonitor-SDK/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers.update(headers)
        
        _logger.info(f"MonitorClient initialized for project: {self.project_id}")
    
    def send_event(self, 
                   action: str, 
                   metadata: Optional[Dict[str, Any]] = None,
                   page_url: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None):
        """
        Отправляет событие в формате, совместимом с API.
        
        Args:
            action: Действие (например, "flask_exception", "user_action")
            metadata: Метаданные события (всё, что не входит в context)
            page_url: URL страницы (если есть)
            context: Дополнительный контекст (переопределяет глобальный)
        """
        try:
            user_id = self.user_id_func() if self.user_id_func else "anonymous"
        except Exception:
            user_id = "anonymous"

        # Объединяем контексты
        final_context = {
            "platform": "backend",
            "language": "python",
            "os_family": self._detect_os(),
            "browser_family": "server",
            **self.context,
            **(context or {})
        }

        # Формируем payload в формате API
        payload = {
            "project_id": self.project_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "context": {
                "platform": final_context.get("platform", "backend"),
                "language": final_context.get("language", "python"),
                "os_family": final_context.get("os_family", "Linux"),
                "browser_family": final_context.get("browser_family", "server")
            },
            "meta": {
                # Всё остальное кладём в meta
                "user_id": user_id,
                "page_url": page_url or "server-side",
                "sdk_version": "1.0.0",
                **metadata  # Все пользовательские метаданные
            }
        }

        # Добавляем всё из context в meta (кроме основных полей)
        for key, value in final_context.items():
            if key not in ["platform", "language", "os_family", "browser_family"]:
                payload["meta"][f"context_{key}"] = value

        # Отправляем асинхронно
        try:
            thread = threading.Thread(
                target=self._send_sync,
                args=(payload,),
                daemon=True
            )
            thread.start()
            _logger.debug(f"Event queued: {action}")
        except Exception as e:
            _logger.warning(f"Failed to queue event: {e}")

    def capture_exception(self, 
                          exception: Exception, 
                          metadata: Optional[Dict[str, Any]] = None,
                          page_url: Optional[str] = None):
        """
        Отправляет информацию об исключении.
        
        Args:
            exception: Объект исключения
            metadata: Дополнительные метаданные
            page_url: URL страницы
        """
        # Получаем информацию об исключении
        exc_type = type(exception).__name__
        exc_message = str(exception)
        exc_traceback = traceback.format_exc()
        
        # Формируем метаданные с информацией об ошибке
        error_metadata = {
            "exception_type": exc_type,
            "error_message": exc_message,
            "traceback": exc_traceback,
            **(metadata or {})
        }
        
        # Отправляем как событие
        self.send_event(
            action=f"exception: {exc_type}",
            metadata=error_metadata,
            page_url=page_url
        )

    def _detect_os(self) -> str:
        """Определяет операционную систему"""
        import platform
        system = platform.system().lower()
        if system == "windows":
            return "Windows"
        elif system == "darwin":
            return "macOS"
        elif system == "linux":
            return "Linux"
        else:
            return "Unknown"

    def _send_sync(self, payload: dict):
        """Синхронная отправка события (в отдельном потоке)"""
        try:
            _logger.debug(f"Sending event to {self.endpoint}/track")
            
            response = self.session.post(
                f"{self.endpoint}/track",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                _logger.debug(f"Event sent successfully: {response.status_code}")
            else:
                _logger.warning(f"Failed to send event: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            _logger.warning(f"Connection error: {self.endpoint} is not available")
        except requests.exceptions.Timeout:
            _logger.warning(f"Timeout sending event to {self.endpoint}")
        except Exception as e:
            _logger.warning(f"Failed to send event: {e}")

    def set_context(self, **kwargs):
        """Добавляет/обновляет глобальный контекст"""
        self.context.update(kwargs)
        _logger.debug(f"Context updated: {kwargs}")

    def clear_context(self):
        """Очищает глобальный контекст"""
        self.context.clear()
        _logger.debug("Context cleared")


# Глобальный клиент
_client: Optional[MonitorClient] = None


def get_client() -> Optional[MonitorClient]:
    """Текущий клиент после init_monitor. Интеграции должны вызывать это, а не импортировать _client."""
    return _client


def init_monitor(
    endpoint: str,
    project_id: str = "default-project",
    user_id_func: Optional[Callable] = None,
    context: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
):
    """
    Инициализирует SDK.
    
    Args:
        endpoint: Базовый URL Collector API (например, "http://localhost:8000")
        project_id: Идентификатор проекта
        user_id_func: Функция для получения user_id
        context: Контекст по умолчанию (язык, ОС и т.д.)
        api_key: Секрет для COLLECTOR_REQUIRE_API_KEY (Bearer / совместим с X-Api-Key на сервере)
    
    Example:
        >>> def get_user():
        ...     return request.remote_addr if request else "anonymous"
        >>> init_monitor(
        ...     endpoint="http://localhost:8000",
        ...     project_id="my-flask-app",
        ...     user_id_func=get_user,
        ...     context={"environment": "production"}
        ... )
    """
    global _client
    _client = MonitorClient(
        endpoint=endpoint,
        project_id=project_id,
        user_id_func=user_id_func,
        context=context or {},
        api_key=api_key,
    )
    _logger.info(f"ErrorMonitor SDK initialized for {endpoint} (project: {project_id})")
    return _client

def track_event(action: str, 
                metadata: Optional[Dict[str, Any]] = None,
                page_url: Optional[str] = None):
    """
    Отправляет событие вручную.
    
    Args:
        action: Действие (например, "user_login", "file_upload")
        metadata: Метаданные события
        page_url: URL страницы
    
    Example:
        >>> track_event(
        ...     action="file_upload",
        ...     metadata={"filename": "test.txt", "size": 1024},
        ...     page_url="http://example.com/upload"
        ... )
    """
    if _client is None:
        raise RuntimeError("Call init_monitor() first")
    _client.send_event(action=action, metadata=metadata, page_url=page_url)

def capture_exception(exception: Exception, 
                     metadata: Optional[Dict[str, Any]] = None,
                     page_url: Optional[str] = None):
    """
    Отправляет информацию об исключении.
    
    Args:
        exception: Объект исключения
        metadata: Дополнительные метаданные
        page_url: URL страницы
    
    Example:
        >>> try:
        ...     1/0
        ... except Exception as e:
        ...     capture_exception(e, metadata={"user_id": "123"})
    """
    if _client is None:
        _logger.warning("SDK not initialized, exception not captured")
        return
    _client.capture_exception(exception=exception, metadata=metadata, page_url=page_url)

def set_context(**kwargs):
    """Устанавливает глобальный контекст для всех последующих событий"""
    if _client is None:
        raise RuntimeError("Call init_monitor() first")
    _client.set_context(**kwargs)

def clear_context():
    """Очищает глобальный контекст"""
    if _client is None:
        raise RuntimeError("Call init_monitor() first")
    _client.clear_context()