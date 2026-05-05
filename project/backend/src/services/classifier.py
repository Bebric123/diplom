import json
import logging
import re
import time
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Жёстко: ровно один JSON-объект; API: OPEN_WEBUI_RESPONSE_FORMAT=off|json_object|json_schema
_MERGED_JSON_RULES = (
    "По кратким данным об инциденте ответь ТОЛЬКО валидным JSON-объектом на русском, без markdown, без пояснений вне JSON, "
    "первый символ «{», последний «}». "
    "Ключи строго: severity, criticality, recommendation (строка). "
    "severity — одно из: незначительно, низкая, средняя, высокая, критическая. "
    "criticality — одно из: можно не исправлять, не критично, требует внимания, блокирует функционал, авария. "
    "recommendation — 3-4 коротких предложения: суть и что проверить, по фактам из данных. "
    "Никакого другого текста кроме объекта JSON."
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

    return _build_error_summary_compact(
        page_url, action, context, metadata
    ).strip()


def _build_error_summary_compact(
    page_url: str,
    action: str,
    context: dict,
    metadata: dict,
) -> str:
    """Краткие данные для LLM — меньше токенов, стабильнее JSON."""
    err_line: list[str] = []
    if metadata.get("error_file") is not None or metadata.get("error_line") is not None:
        el = []
        if metadata.get("error_file") is not None:
            el.append(f"file={metadata.get('error_file')}")
        if metadata.get("error_line") is not None:
            el.append(f"line={metadata.get('error_line')}")
        if metadata.get("error_column") is not None:
            el.append(f"col={metadata.get('error_column')}")
        err_line.append("Источник: " + ", ".join(el))

    error_message = metadata.get("error_message", "No error message")
    if metadata.get("exception_type") or metadata.get("name"):
        t = str(metadata.get("exception_type") or metadata.get("name") or "")
        if t and t not in (error_message or ""):
            err_line.append("Тип: " + t)
    if metadata.get("status_code") is not None:
        err_line.append(f"HTTP status: {metadata.get('status_code')}")
    if metadata.get("user_id"):
        err_line.append(f"user_id: {str(metadata.get('user_id'))[:120]}")
    cs = metadata.get("component_stack")
    if cs:
        err_line.append("component_stack: " + str(cs)[:800])

    stack_src = (metadata.get("stack_trace") or metadata.get("error_stack") or "") or ""
    stack_trace = stack_src[:1500]
    if len(stack_src) > 1500:
        err_line.append(f"… (стек обрезан, всего {len(stack_src)} симв.)")

    _META_CAP = 2400
    try:
        _meta_full = json.dumps(metadata, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        _meta_full = str(metadata)
    meta_json = _meta_full[:_META_CAP]
    if len(_meta_full) > _META_CAP:
        meta_json += f"\n… (meta > {_META_CAP} симв.)"

    try:
        ctx_s = json.dumps(context, ensure_ascii=False, default=str)[:800]
    except (TypeError, ValueError):
        ctx_s = str(context)[:800]

    err_extra = "\n" + "\n".join(err_line) if err_line else ""

    return f"""
URL: {page_url}
Действие: {action}
Платформа: {context.get('platform', 'unknown')}, язык: {context.get('language', 'javascript')},
ОС: {context.get('os_family', 'unknown')}, браузер/рантайм: {context.get('browser_family', 'unknown')}
Ошибка: {error_message}
Стек (фрагмент): {stack_trace}
{err_extra}
Контекст: {ctx_s}
Доп. meta: {meta_json}
"""


def _build_llm_user_text(event: dict) -> str:
    summary = _build_error_summary(event)
    text = f"""{_MERGED_JSON_RULES}

Пример: {{"severity":"низкая","criticality":"не требует внимания","recommendation":"GET / — 404; проверьте маршруты."}}

Данные:
{summary}"""
    if get_settings().open_webui_no_think:
        return text.rstrip() + "\n\n/no_think"
    return text


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


def _first_russian_token(s: str) -> str:
    t = (s or "").strip().strip("«»\"'")
    if not t:
        return ""
    return t.split()[0] if t.split() else t


def _word_to_severity(urgency_word: str) -> str:
    """Одно слово «срочность» -> severity."""
    w = _first_russian_token(urgency_word).lower()
    m = {
        "низкая": "низкая",
        "низкий": "низкая",
        "низкое": "низкая",
        "незначительная": "низкая",
        "незначительно": "низкая",
        "средняя": "средняя",
        "средний": "средняя",
        "средне": "средняя",
        "умеренная": "средняя",
        "высокая": "высокая",
        "высокий": "высокая",
        "срочно": "высокая",
        "срочная": "высокая",
        "критическая": "критическая",
        "критично": "критическая",
        "критичный": "критическая",
        "максимальная": "критическая",
        "максимальный": "критическая",
        "немедленно": "критическая",
        "мгновенно": "критическая",
        "low": "низкая",
        "medium": "средняя",
        "high": "высокая",
        "critical": "критическая",
    }
    return m.get(w, "средняя")


def _word_to_criticality(impact_word: str) -> str:
    """Одно слово «критичность» (влияние) -> criticality для БД."""
    w = _first_russian_token(impact_word).lower()
    m = {
        "низкая": "не требует внимания",
        "низкий": "не требует внимания",
        "незначительная": "не требует внимания",
        "незначительно": "не требует внимания",
        "плановая": "не требует внимания",
        "средняя": "требует внимания",
        "средний": "требует внимания",
        "умеренная": "требует внимания",
        "высокая": "требует внимания",
        "высокий": "требует внимания",
        "серьёзная": "требует внимания",
        "серьезная": "требует внимания",
        "существенная": "требует внимания",
        "критическая": "критично",
        "критично": "критично",
        "критичный": "критично",
        "аварийная": "критично",
        "фатальная": "критично",
        "low": "не требует внимания",
        "medium": "требует внимания",
        "high": "требует внимания",
        "critical": "критично",
    }
    return m.get(w, "требует внимания")


def _coerce_parsed_to_pipeline_dict(parsed: dict) -> dict:
    """
    Ожидаем жёсткий набор: severity, criticality, recommendation.
    Дополнительно: пара критичность+срочность (одно слово) — на случай устаревшего ответа модели.
    """
    rec = str(parsed.get("recommendation", "") or "").strip()
    if not rec:
        raise ValueError("Нет recommendation")

    if all(k in parsed for k in ("severity", "criticality", "recommendation")):
        return {
            "severity": str(parsed["severity"]).strip(),
            "criticality": str(parsed["criticality"]).strip(),
            "recommendation": rec,
        }

    k_imp: Optional[str] = None
    k_urg: Optional[str] = None
    for key in ("критичность", "impact", "importance"):
        v = parsed.get(key)
        if v is not None and str(v).strip():
            k_imp = v
            break
    for key in ("срочность", "urgency"):
        v = parsed.get(key)
        if v is not None and str(v).strip():
            k_urg = v
            break
    if k_imp is not None and k_urg is not None:
        return {
            "severity": _word_to_severity(str(k_urg)),
            "criticality": _word_to_criticality(str(k_imp)),
            "recommendation": rec,
        }
    raise ValueError("Нужны severity, criticality, recommendation")


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
    return _coerce_parsed_to_pipeline_dict(parsed)


def _try_parse_json_flexible(raw: str) -> Optional[dict]:
    """Валидный JSON целиком или первый объект {{…}} внутри длинного ответа."""
    if not raw or not str(raw).strip():
        return None
    try:
        return _parse_json_response(raw)
    except (ValueError, json.JSONDecodeError, TypeError):
        pass
    try:
        cleaned = _strip_think_and_fences(raw)
        blob = _first_balanced_json_object(cleaned)
        if not blob:
            return None
        parsed = json.loads(blob)
        if isinstance(parsed, dict):
            return _coerce_parsed_to_pipeline_dict(parsed)
    except (ValueError, json.JSONDecodeError, TypeError):
        pass
    return None


def _prose_llm_fallback(raw: str, event: dict) -> dict:
    """Текст модели без JSON — в recommendation; степени — эвристика по событию."""
    h = _heuristic_classify(event)
    text = (raw or "").strip()
    if len(text) > 3500:
        text = text[:3497] + "..."
    return {
        "severity": h["severity"],
        "criticality": h["criticality"],
        "recommendation": f"Модель (текст без JSON):\n\n{text}",
    }


def _heuristic_blob_for_match(event: dict) -> str:
    """Сводка на случай, когда нет валидного JSON от LLM: шире, чем 2–3 ключа, чтобы «типичный» стек
    не попадал в безымянный default."""
    meta = event.get("meta") or {}
    ctx = event.get("context") or {}
    try:
        m = json.dumps(meta, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        m = str(meta)
    try:
        c = json.dumps(ctx, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        c = str(ctx)
    s = f"{event.get('action', '')} {event.get('page_url', '')} {c} {m}"
    return s.lower()


def _heuristic_classify(event: dict) -> dict:
    """Если LLM деградирует или не отдаёт JSON — разумные значения по тексту события."""
    meta = event.get("meta") or {}
    parts = []
    for key in ("error_message", "first_errors", "stack_trace", "error_stack"):
        v = meta.get(key)
        if v:
            parts.append(str(v))
    blob = _heuristic_blob_for_match(event)
    blob_short = " ".join(parts).lower() if parts else ""
    if len(blob_short.strip()) < 8:
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
        " typeerror",
        " referenceerror",
        " syntaxerror",
        " unhandledrejection",
        "err_network",
        " uncaught",
        " at error",
        "at http",
        "at https",
        "ошибка",
        "исключ",
        "стек",
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
        "recommendation": (
            "Сработала встроенная оценка без нейросети (сбой/некорректный JSON Open WebUI или нет "
            "совпадения с эвристическими правилами). Смотрите error_message, стек и поле meta в карточке; "
            "логи worker — по строкам «open_webui attempt failed»."
        ),
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


def _analyze_open_webui(event: dict) -> dict:
    from src.services import open_webui_client

    s = get_settings()
    base = (s.open_webui_base_url or "").strip().rstrip("/")
    model = (s.open_webui_model or "").strip()
    if not base:
        return _fallback(ValueError("OPEN_WEBUI_BASE_URL не задан"))
    if not model:
        return _fallback(ValueError("OPEN_WEBUI_MODEL не задан (имя модели как в Open WebUI)"))

    user_text = _build_llm_user_text(event)
    messages = [{"role": "user", "content": user_text}]
    path = (s.open_webui_chat_completions_path or "/api/chat/completions").strip()
    api_key = (s.open_webui_api_key or "").strip()
    last_err: Exception | None = None
    for attempt in range(2):
        raw = ""
        try:
            raw = open_webui_client.chat_completion(
                base_url=base,
                completions_path=path,
                api_key=api_key,
                model=model,
                messages=messages,
                max_tokens=s.open_webui_max_tokens,
                temperature=s.open_webui_temperature,
                response_format=s.open_webui_response_format,
                timeout_sec=s.open_webui_timeout_sec,
            )
            if not (raw or "").strip():
                raise ValueError("Пустой ответ модели")
            if _looks_degenerate(raw):
                raise ValueError("Деградированный повторяющийся ответ модели")
            parsed = _try_parse_json_flexible(raw)
            if parsed:
                return parsed
            logger.info(
                "open_webui: в ответе нет JSON — используем сырой текст в recommendation"
            )
            return _prose_llm_fallback(raw, event)
        except Exception as e:
            last_err = e
            preview = (raw[:500] + "…") if len(raw) > 500 else raw
            logger.warning(
                "open_webui attempt %s failed: %s | фрагмент ответа: %r",
                attempt + 1,
                e,
                preview or "(пусто)",
            )
            if attempt == 0:
                time.sleep(0.3)
    h = _heuristic_classify(event)
    logger.info("open_webui: эвристика вместо ответа модели (последняя ошибка: %s)", last_err)
    return h


def _analyze_none(_event: dict) -> dict:
    return {
        "severity": "средняя",
        "criticality": "требует внимания",
        "recommendation": "Автоматический анализ отключён (ERROR_ANALYSIS_BACKEND=none).",
    }


def analyze_error(event: dict) -> dict:
    s = get_settings()
    backend = (s.error_analysis_backend or "open_webui").strip().lower()
    if backend in ("none", "off", "disabled"):
        return _analyze_none(event)
    if backend not in ("open_webui", "webui"):
        logger.warning("Неизвестный ERROR_ANALYSIS_BACKEND=%r, используется open_webui", backend)
    return _analyze_open_webui(event)
