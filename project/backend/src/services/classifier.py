import json
import re
import time
import requests

from .gigachat_auth import GigaChatAuth

auth = GigaChatAuth()
_GIGA_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


def analyze_error_with_gigachat(event: dict) -> dict:
    context = dict(event.get("context") or {})
    metadata = event.get("meta") or {}
    page_url = event.get("page_url", "N/A")
    action = event.get("action", "unknown")

    if action == "log_analysis" or metadata.get("first_errors") is not None:
        fn = metadata.get("filename", "")
        ec = metadata.get("errors_count", 0)
        wc = metadata.get("warnings_count", 0)
        body = str(metadata.get("first_errors") or "")[:8000]
        error_summary = f"""
Тип: загруженный лог-файл (не веб-страница).
Файл: {fn}
URL/идентификатор в системе: {page_url}
Строк с маркерами error/exception/critical: {ec}
Строк с warning: {wc}
Текст из лога (как при анализе):
{body}
""".strip()
    else:
        user_agent = metadata.get("user_agent", "")
        if not context.get("browser_family") and user_agent:
            browser = "Chrome" if "Chrome" in user_agent else "Firefox" if "Firefox" in user_agent else "Other"
            os_family = "Windows" if "Windows" in user_agent else "Mac" if "Mac" in user_agent else "Linux"
            context.setdefault("browser_family", browser)
            context.setdefault("os_family", os_family)

        error_message = metadata.get("error_message", "No error message")
        stack_trace = (metadata.get("stack_trace") or metadata.get("error_stack") or "")[:500]

        error_summary = f"""
URL: {page_url}
Действие: {action}
Платформа: {context.get('platform', 'unknown')}
Язык: {context.get('language', 'javascript')}
ОС: {context.get('os_family', 'unknown')}
Браузер: {context.get('browser_family', 'unknown')}
Ошибка: {error_message}
Стек: {stack_trace}
""".strip()

    prompt = f"""
Ты — эксперт по анализу ошибок в веб-приложениях.
Проанализируй ошибку ниже и ответь ТОЛЬКО в формате JSON без пояснений, без markdown.

Правила:
- Используй ТОЛЬКО информацию из описания ошибки.
- severity: одно из ["незначительно", "низкая", "средняя", "высокая", "критическая"]
- criticality: одно из ["можно не исправлять", "не критично", "требует внимания", "блокирует функционал", "авария"]
- recommendation: кратко (1–2 предложения на русском).

Описание ошибки:
{error_summary}

Ответ строго: {{"severity": "...", "criticality": "...", "recommendation": "..."}}
"""

    payload = {
        "model": "GigaChat-2-Pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 400,
    }

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            access_token = auth.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            response = requests.post(
                _GIGA_URL,
                json=payload,
                headers=headers,
                verify=auth.verify_ssl,
                timeout=20,
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            json_match = re.search(r"\{.*\}", result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if all(k in parsed for k in ["severity", "criticality", "recommendation"]):
                    return parsed
            raise ValueError("Неполный JSON")
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(0.5)
                continue

    return {
        "severity": "средняя",
        "criticality": "требует внимания",
        "recommendation": f"Ошибка ИИ: {str(last_err)[:100] if last_err else 'unknown'}",
    }
