"""
Локальный вывод из GGUF через llama-cpp-python (данные не уходят в интернет).
GGUF — для llama.cpp; путь задаётся LOCAL_LLM_GGUF_PATH.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Схема для LlamaGrammar: только три поля, допустимые значения severity/criticality на русском.
_INCIDENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "severity": {
            "type": "string",
            "enum": ["незначительно", "низкая", "средняя", "высокая", "критическая"],
        },
        "criticality": {
            "type": "string",
            "enum": [
                "можно не исправлять",
                "не критично",
                "требует внимания",
                "блокирует функционал",
                "авария",
            ],
        },
        "recommendation": {"type": "string", "maxLength": 800},
    },
    "required": ["severity", "criticality", "recommendation"],
}

_grammar_instance: Any = None
_grammar_load_attempted: bool = False


def _get_incident_json_grammar():
    """Один раз на процесс; при ошибке — None, дальше без грамматики."""
    global _grammar_instance, _grammar_load_attempted
    if _grammar_load_attempted:
        return _grammar_instance
    _grammar_load_attempted = True
    try:
        from llama_cpp import LlamaGrammar  # type: ignore

        _grammar_instance = LlamaGrammar.from_json_schema(
            json.dumps(_INCIDENT_JSON_SCHEMA, ensure_ascii=False),
            verbose=False,
        )
        logger.info("LLM: включена JSON-грамматика классификации инцидентов")
    except Exception as e:
        logger.warning("LLM: JSON-грамматика недоступна (%s), свободная генерация", e)
        _grammar_instance = None
    return _grammar_instance

_llama = None
_llama_path: Optional[str] = None
_lock = threading.Lock()


def _try_import_llama():
    try:
        from llama_cpp import Llama  # type: ignore

        return Llama
    except ImportError as e:
        raise ImportError(
            "Для локального GGUF установите: pip install llama-cpp-python "
            "(см. backend/requirements/local_llm.txt). Оригинальная ошибка: "
            f"{e}"
        ) from e


def get_llama(model_path: str, n_ctx: int, n_threads: int, n_gpu_layers: int):
    """Ленивая загрузка одной модели на процесс (потокобезопасно)."""
    global _llama, _llama_path
    Llama = _try_import_llama()
    with _lock:
        if _llama is not None and _llama_path == model_path:
            return _llama
        if _llama is not None and _llama_path != model_path:
            logger.warning("Перезагрузка GGUF: путь модели изменился с %s на %s", _llama_path, model_path)
            del _llama
            _llama = None
        logger.info("Загрузка GGUF: %s (n_ctx=%s, n_gpu_layers=%s)", model_path, n_ctx, n_gpu_layers)
        kwargs = {
            "model_path": model_path,
            "n_ctx": n_ctx,
            "verbose": False,
            "n_gpu_layers": n_gpu_layers,
        }
        if n_threads and n_threads > 0:
            kwargs["n_threads"] = n_threads
        _llama = Llama(**kwargs)
        _llama_path = model_path
        return _llama


def generate_completion(
    model_path: str,
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    n_ctx: int = 8192,
    max_tokens: int = 512,
    temperature: float = 0.1,
    repeat_penalty: float = 1.0,
    top_p: float = 0.92,
    n_threads: int = 0,
    n_gpu_layers: int = 0,
    json_grammar: bool = False,
) -> str:
    llm = get_llama(model_path, n_ctx, n_threads, n_gpu_layers)
    messages = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt})
    effective_max = max_tokens
    kwargs = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": effective_max,
        "top_p": top_p,
    }
    if repeat_penalty and repeat_penalty > 1.0:
        kwargs["repeat_penalty"] = repeat_penalty
    if json_grammar:
        g = _get_incident_json_grammar()
        if g is not None:
            kwargs["grammar"] = g
            # С грамматикой ответ короткий; меньше токенов — быстрее на CPU
            kwargs["max_tokens"] = min(effective_max, 384)
    out = llm.create_chat_completion(**kwargs)
    choice = (out.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text and choice.get("text"):
        text = str(choice["text"]).strip()
    return text
