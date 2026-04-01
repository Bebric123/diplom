import json
import logging
import re
import time
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Один user-текст (без отдельного system): часть шаблонов + IQ1 ломается на «двух ролях».
_MERGED_JSON_RULES = (
    "Классифицируй инцидент по приведённым данным. Ответь ОДНИМ JSON на русском, без markdown и без текста вокруг. "
    "Ключи: severity, criticality, recommendation. "
    'severity — одно из: незначительно, низкая, средняя, высокая, критическая (по реальной тяжести для пользователя/сервиса). '
    'criticality — одно из: можно не исправлять, не критично, требует внимания, '
    "блокирует функционал, авария. "
    "recommendation — 1–2 коротких предложения: назови конкретику из данных "
    "(тип ошибки, фрагмент стека, URL, файл лога, сервис). "
    "Запрещены общие формулировки без привязки к инциденту, например: "
    "«проверка на основе данных», «необходимо проверить систему», «проанализировать ситуацию» без указания что именно проверять."
)


def _build_error_summary(event: dict) -> str:
    context = dict(event.get("context") or {})
    metadata = event.get("meta") or {}
    page_url = event.get("page_url", "N/A")
    action = event.get("action", "unknown")

    if action == "log_analysis" or metadata.get("first_errors") is not None:
        fn = metadata.get("filename", "")
        ec = metadata.get("errors_count", 0)
        wc = metadata.get("warnings_count", 0)
        body = str(metadata.get("first_errors") or "")[:8000]
        return f"""
Тип: загруженный лог-файл.
Файл: {fn}
Идентификатор: {page_url}
Строк error/exception/critical: {ec}, warning: {wc}
Фрагмент лога:
{body}
""".strip()

    user_agent = metadata.get("user_agent", "")
    if not context.get("browser_family") and user_agent:
        browser = "Chrome" if "Chrome" in user_agent else "Firefox" if "Firefox" in user_agent else "Other"
        os_family = "Windows" if "Windows" in user_agent else "Mac" if "Mac" in user_agent else "Linux"
        context.setdefault("browser_family", browser)
        context.setdefault("os_family", os_family)

    error_message = metadata.get("error_message", "No error message")
    stack_trace = (metadata.get("stack_trace") or metadata.get("error_stack") or "")[:500]

    return f"""
URL: {page_url}
Действие: {action}
Платформа: {context.get('platform', 'unknown')}
Язык: {context.get('language', 'javascript')}
ОС: {context.get('os_family', 'unknown')}
Браузер: {context.get('browser_family', 'unknown')}
Ошибка: {error_message}
Стек: {stack_trace}
""".strip()


def _build_llm_user_text(event: dict) -> str:
    summary = _build_error_summary(event)
    return f"""{_MERGED_JSON_RULES}

Пример: {{"severity":"средняя","criticality":"требует внимания","recommendation":"Проверить обработчик POST /api/orders: в стеке TypeError при разборе JSON тела запроса."}}

Данные:
{summary}

Только JSON, первый символ «{{», последний «}}»."""


def _strip_think_and_fences(text: str) -> str:
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    s = re.sub(r"\u003cthink\u003e[\s\S]*?\u003c/think\u003e", "", s, flags=re.I)
    s = re.sub(
        r"\u003credacted_reasoning\u003e[\s\S]*?\u003c/redacted_reasoning\u003e",
        "",
        s,
        flags=re.I,
    )
    return s.strip()


def _looks_degenerate(text: str) -> bool:
    """Ранний отсев зацикленного вывода (IQ1 / Thinking)."""
    if not text or len(text) < 120:
        return False
    head = text[:2400]
    if head.count("ошибка") >= 12 or head.lower().count("error") >= 12:
        return True
    chunk = text[80:160]
    if len(chunk) >= 24 and text.count(chunk) >= 4:
        return True
    return False


def _looks_meta_without_json(text: str) -> bool:
    """Рассуждения о задании вместо объекта (часто Thinking / слабый квант), без «{» в начале."""
    if not text or len(text) < 50:
        return False
    head = text.strip()[:1400]
    if "{" in head:
        return False
    low = head.lower()
    hints = (
        "we are given",
        "the task at hand",
        "json object",
        "following structur",
        "classify the incident",
        "output an object",
        "specified the following",
    )
    return any(h in low for h in hints)


def _first_balanced_json_object(s: str) -> Optional[str]:
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    quote = ""
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                in_str = False
            continue
        if c in "\"'":
            in_str = True
            quote = c
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _parse_json_response(result: str) -> dict:
    cleaned = _strip_think_and_fences(result)
    blob = _first_balanced_json_object(cleaned)
    if not blob:
        blob = cleaned.strip()
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}\s*$", cleaned)
        if not m:
            raise ValueError("В ответе нет JSON")
        parsed = json.loads(m.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON не объект")
    if not all(k in parsed for k in ["severity", "criticality", "recommendation"]):
        raise ValueError("Неполный JSON")
    return parsed


def _heuristic_classify(event: dict) -> dict:
    """Если LLM деградирует или не отдаёт JSON — разумные значения по тексту события."""
    meta = event.get("meta") or {}
    parts = []
    for key in ("error_message", "first_errors", "stack_trace", "error_stack"):
        v = meta.get(key)
        if v:
            parts.append(str(v))
    blob = " ".join(parts).lower()
    if len(blob.strip()) < 8:
        return {
            "severity": "низкая",
            "criticality": "не критично",
            "recommendation": "Мало данных; откройте событие в интерфейсе и при необходимости загрузите лог.",
        }

    critical = (
        "fatal",
        "panic",
        "segfault",
        "corrupt",
        "критическ",
        "авари",
        "econnrefused",
        "connection refused",
        "database",
        "postgres",
        "deadlock",
    )
    high = (
        "timeout",
        "таймаут",
        " 500 ",
        " 502 ",
        " 503 ",
        " 504 ",
        "exception",
        "traceback",
        "undefined is not",
        "cannot read prop",
        "internal server",
    )
    low = ("warning", "deprecated", "404", "not found", "403", "forbidden", "console.warn")

    if any(p in blob for p in critical):
        return {
            "severity": "критическая",
            "criticality": "авария",
            "recommendation": "Проверить логи, доступность БД и внешних сервисов; воспроизвести на стенде.",
        }
    if any(p in blob for p in high):
        return {
            "severity": "высокая",
            "criticality": "блокирует функционал",
            "recommendation": "Разобрать стек и условия воспроизведения; проверить недавние деплои и конфигурацию.",
        }
    if any(p in blob for p in low) and not any(p in blob for p in high):
        return {
            "severity": "низкая",
            "criticality": "не критично",
            "recommendation": "Точечная проверка: маршрут, права доступа или устаревший вызов API.",
        }
    return {
        "severity": "средняя",
        "criticality": "требует внимания",
        "recommendation": "Просмотреть сообщение об ошибке и связанный контекст в мониторинге.",
    }


def _fallback(last_err: Exception | None) -> dict:
    return {
        "severity": "средняя",
        "criticality": "требует внимания",
        "recommendation": (
            f"Ошибка ИИ: {str(last_err)[:200]}"
            if last_err
            else "Анализ недоступен"
        ),
    }


def _analyze_local_gguf(event: dict) -> dict:
    from src.services import local_gguf_llm

    s = get_settings()
    path = (s.local_llm_gguf_path or "").strip()
    if not path:
        return _fallback(ValueError("LOCAL_LLM_GGUF_PATH не задан"))

    user_text = _build_llm_user_text(event)
    n_ctx = s.local_llm_n_ctx
    max_tok = s.local_llm_max_tokens
    grammar_cap = 256
    if s.local_llm_fast_mode:
        max_tok = min(max_tok, 256)
        grammar_cap = 192
    last_err: Exception | None = None
    for attempt in range(2):
        raw = ""
        try:
            raw = local_gguf_llm.generate_completion(
                path,
                user_text,
                system_prompt=None,
                n_ctx=n_ctx,
                max_tokens=max_tok,
                temperature=0.05,
                repeat_penalty=s.local_llm_repeat_penalty,
                n_threads=s.local_llm_n_threads,
                n_gpu_layers=s.local_llm_n_gpu_layers,
                json_grammar=s.local_llm_json_grammar,
                json_grammar_max_tokens=grammar_cap,
            )
            if _looks_meta_without_json(raw):
                raise ValueError("Модель выдала рассуждения вместо JSON")
            if _looks_degenerate(raw):
                raise ValueError("Деградированный повторяющийся ответ модели")
            return _parse_json_response(raw)
        except Exception as e:
            last_err = e
            preview = (raw[:500] + "…") if len(raw) > 500 else raw
            logger.warning(
                "local_gguf attempt %s failed: %s | фрагмент ответа: %r",
                attempt + 1,
                e,
                preview or "(пусто)",
            )
            if attempt == 0:
                time.sleep(0.3)
    h = _heuristic_classify(event)
    logger.info("local_gguf: эвристика вместо ответа модели (последняя ошибка: %s)", last_err)
    return h


def _analyze_none(_event: dict) -> dict:
    return {
        "severity": "средняя",
        "criticality": "требует внимания",
        "recommendation": "Автоматический анализ отключён (ERROR_ANALYSIS_BACKEND=none).",
    }


def analyze_error(event: dict) -> dict:
    s = get_settings()
    backend = (s.error_analysis_backend or "local_gguf").strip().lower()
    if backend in ("none", "off", "disabled"):
        return _analyze_none(event)
    return _analyze_local_gguf(event)
