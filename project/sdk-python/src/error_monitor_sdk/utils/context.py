# error_monitor_sdk/utils/context.py
from typing import Dict, Any, Optional

def get_request_context(request: Any, framework: str) -> Dict[str, Any]:
    """
    Универсальная функция для извлечения контекста из request
    """
    context = {}
    
    try:
        if framework == "fastapi":
            context = {
                "url": str(request.url),
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "path_params": dict(request.path_params),
                "client_host": request.client.host if request.client else None,
                "headers": dict(request.headers)
            }
            
        elif framework == "django":
            context = {
                "url": request.build_absolute_uri(),
                "method": request.method,
                "path": request.path,
                "remote_addr": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "referer": request.META.get("HTTP_REFERER", ""),
                "content_type": request.META.get("CONTENT_TYPE", ""),
                "query_string": request.META.get("QUERY_STRING", "")
            }
            
    except Exception as e:
        context["error_extracting"] = str(e)
    
    return context