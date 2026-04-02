"""
HTTP-клиент к Open WebUI: OpenAI-совместимый POST .../api/chat/completions.
Модель на ПК подключается через веб-интерфейс Open WebUI (Ollama и т.д.) — тут только вызов API.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def chat_completion(
    *,
    base_url: str,
    completions_path: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.05,
    request_json_object: bool = True,
    timeout_sec: float = 180.0,
) -> str:
    """
    Возвращает текст content из choices[0].message.content.
    """
    root = (base_url or "").strip().rstrip("/")
    path = (completions_path or "/api/chat/completions").strip()
    if not path.startswith("/"):
        path = "/" + path
    url = f"{root}{path}"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if request_json_object:
        body["response_format"] = {"type": "json_object"}

    logger.debug("Open WebUI POST %s model=%s", url, model)
    resp = requests.post(url, json=body, headers=headers, timeout=timeout_sec)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = resp.text[:500]
        except Exception:
            pass
        raise RuntimeError(f"Open WebUI HTTP {resp.status_code}: {detail or e}") from e

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Open WebUI: пустой choices в ответе")
    msg = choices[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text and choices[0].get("text"):
        text = str(choices[0]["text"]).strip()
    if not text:
        raise ValueError("Open WebUI: нет текста в ответе")
    return text
