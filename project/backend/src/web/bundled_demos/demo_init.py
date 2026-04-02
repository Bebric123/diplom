"""
Обёртка над error_monitor_sdk.init_monitor для демо.

Если в venv старая сборка без аргумента api_key, вызов не падает.
С актуальным SDK и ключом выполните из каталога examples/sdk-demos/python:

  pip install -e ../../../project/sdk-python
"""
from __future__ import annotations

import inspect
import warnings
from typing import Any, Callable, Dict, Optional

from error_monitor_sdk import init_monitor as _upstream


def init_monitor(
    endpoint: str,
    project_id: str = "default-project",
    user_id_func: Optional[Callable[..., str]] = None,
    context: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
):
    kw: Dict[str, Any] = {
        "endpoint": endpoint,
        "project_id": project_id,
        "user_id_func": user_id_func,
        "context": context,
        "api_key": api_key,
    }
    sig = inspect.signature(_upstream)
    if "api_key" not in sig.parameters:
        if kw.get("api_key"):
            warnings.warn(
                "MONITOR_API_KEY задан, но установленный SDK не поддерживает api_key. "
                "Выполните: pip install -e ../../../project/sdk-python",
                UserWarning,
                stacklevel=2,
            )
        kw.pop("api_key", None)
    kw = {k: v for k, v in kw.items() if k in sig.parameters}
    return _upstream(**kw)
