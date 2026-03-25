import json
import re
import requests
from .gigachat_auth import GigaChatAuth

auth = GigaChatAuth()

def analyze_error_with_gigachat(event: dict) -> dict:
    context = event.get("context", {})
    metadata = event.get("meta", {})  # ← важно: meta, а не metadata
    page_url = event.get("page_url", "N/A")
    action = event.get("action", "unknown")

    # Извлекаем данные из user_agent, если нет в context
    user_agent = metadata.get("user_agent", "")
    if not context.get("browser_family") and user_agent:
        # Можно использовать ua-parser, но для ВКР — упрощённо
        browser = "Chrome" if "Chrome" in user_agent else "Firefox" if "Firefox" in user_agent else "Other"
        os_family = "Windows" if "Windows" in user_agent else "Mac" if "Mac" in user_agent else "Linux"
        context.setdefault("browser_family", browser)
        context.setdefault("os_family", os_family)

    error_message = metadata.get("error_message", "No error message")
    stack_trace = metadata.get("stack_trace", "")[:500]

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
Проанализируй ошибку ниже и ответь ТОЛЬКО в формате JSON без пояснений, без markdown, без лишних слов.

Правила:
- Используй ТОЛЬКО информацию из описания ошибки.
- Не выдумывай детали.
- severity: одно из ["незначительно", "низкая", "средняя", "высокая", "критическая"]
- criticality: одно из ["можно не исправлять", "не критично", "требует внимания", "блокирует функционал", "авария"]
- recommendation: кратко (1–2 предложения на русском): что сломалось и как исправить.

Описание ошибки:
{error_summary}

Ответ строго в формате:
{{"severity": "...", "criticality": "...", "recommendation": "..."}}
"""

    try:
        access_token = auth.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "GigaChat-2-Pro",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,  # ↓ меньше креатива → стабильнее JSON
            "max_tokens": 400
        }

        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            json=payload,
            headers=headers,
            verify=False,
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]

        # Извлекаем JSON даже если есть пояснения до/после
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            # Валидация ключей
            if all(k in parsed for k in ["severity", "criticality", "recommendation"]):
                return parsed

        raise ValueError("Неполный JSON")

    except Exception as e:
        return {
            "severity": "средняя",
            "criticality": "требует внимания",
            "recommendation": f"Ошибка ИИ: {str(e)[:100]}"
        }