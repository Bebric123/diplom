from flask import request
import sys
import traceback
import datetime
from ..client import _client

def enable_flask_integration(app, user_id_func=None):
    """
    Автоматически перехватывает необработанные исключения в Flask-приложении
    и отправляет их в систему мониторинга.
    
    Args:
        app: Flask application instance
        user_id_func: Функция для получения идентификатора пользователя
    """
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        if _client is None:
            app.logger.warning("ErrorMonitor SDK not initialized. Call init_monitor() first.")
            raise

        # Получаем user_id
        user_id = "anonymous"
        if user_id_func:
            try:
                user_id = user_id_func()
            except Exception:
                pass  # Остаёмся на "anonymous"

        # Получаем информацию из request (если доступно)
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
        except:
            pass  # Request может быть недоступен (например, в фоновых задачах)

        # Формируем событие в соответствии с API (из main.py)
        event_data = {
            "project_id": _client.project_id or "default-project",
            "action": f"flask_exception: {type(e).__name__}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "context": {
                "platform": "backend",
                "language": "python",
                "os_family": _client.context.get("os_family", "Linux") if hasattr(_client, 'context') else "Linux",
                "browser_family": "server"
            },
            "meta": {
                # Всё остальное кладём в meta
                "url": page_url,
                "method": method,
                "path": path,
                "user_agent": user_agent,
                "user_id": user_id,
                "exception_type": type(e).__name__,
                "error_message": str(e),
                "traceback": "".join(traceback.format_exception(type(e), e, e.__traceback__)),
                "endpoint": request.endpoint if request and hasattr(request, 'endpoint') else "unknown",
                "remote_addr": request.remote_addr if request else None,
                "content_type": request.headers.get("Content-Type") if request else None,
                "content_length": request.headers.get("Content-Length") if request else None
            }
        }

        # Добавляем дополнительные метаданные из _client.context
        if hasattr(_client, 'context') and _client.context:
            # Добавляем всё из context в meta, но не затираем существующие ключи
            for key, value in _client.context.items():
                if key not in event_data["meta"] and key not in ["platform", "language", "os_family"]:
                    event_data["meta"][f"custom_{key}"] = value

        app.logger.info(f"📤 Sending error event to monitoring: {type(e).__name__}")

        # Отправляем напрямую через _client
        try:
            if hasattr(_client, '_send_sync'):
                _client._send_sync(event_data)
            elif hasattr(_client, 'send_event'):
                # Если есть send_event, используем его
                _client.send_event(event_data)
            else:
                # Пробуем напрямую через requests
                import requests
                requests.post(
                    f"{_client.api_url}/track",
                    json=event_data,
                    headers={"Content-Type": "application/json"},
                    timeout=2
                )
            app.logger.info("✅ Error event sent successfully")
        except Exception as send_err:
            app.logger.error(f"❌ Failed to send error event: {send_err}")

        # Важно: не перехватываем исключение — Flask сам вернёт 500
        raise