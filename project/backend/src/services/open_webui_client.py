"""
HTTP-клиент к Open WebUI: OpenAI-совместимый POST .../api/chat/completions.
Модель на ПК подключается через веб-интерфейс Open WebUI (Ollama и т.д.) — тут только вызов API.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Для response_format type=json_schema (бэкенды, где json_object не поддержан)
_INCIDENT_JSON_SCHEMA: dict[str, Any] = {
    "name": "incident_classification",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "severity": {
                "type": "string",
                "description": "Незначительно, низкая, средняя, высокая, критическая",
            },
            "criticality": {
                "type": "string",
                "description": "Критичность для продукта",
            },
            "recommendation": {"type": "string", "description": "Короткий совет"},
        },
        "required": ["severity", "criticality", "recommendation"],
        "additionalProperties": False,
    },
}


def _apply_response_format(body: dict[str, Any], mode: str) -> None:
    m = (mode or "off").strip().lower()
    if m in ("", "off", "none", "false", "0"):
        return
    if m == "json_object":
        body["response_format"] = {"type": "json_object"}
        return
    if m in ("json_schema", "schema", "structured"):
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": _INCIDENT_JSON_SCHEMA,
        }
        return
    logger.warning("open_webui: неизвестный response_format=%r — без response_format", mode)


def chat_completion(
    *,
    base_url: str,
    completions_path: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.05,
    response_format: str = "off",
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
    _apply_response_format(body, response_format)

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
    # Qwen-思考 / o1-стиль: весь ответ в reasoning_content, content пустой
    if not text:
        for key in ("reasoning_content", "reasoning", "reasoningText"):
            alt = msg.get(key)
            if alt:
                text = str(alt).strip()
                if text:
                    logger.info(
                        "Open WebUI: пустой content, используем %s (%s симв.)", key, len(text)
                    )
                break
    if not text:
        raise ValueError("Open WebUI: нет текста в ответе (и content, и reasoning пусто)")
    return text
