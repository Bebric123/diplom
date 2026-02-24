import json
import re
import os
import requests
from .gigachat_auth import GigaChatAuth

auth = GigaChatAuth()

def analyze_error_with_gigachat(event: dict) -> dict:
    context = event.get("context", {})
    metadata = event.get("metadata", {})

    error_summary = f"""
Платформа: {context.get('platform', 'unknown')}
Язык: {context.get('language', 'unknown')}
Ошибка: {metadata.get('error_message', 'no message')}
Стек: {metadata.get('stack_trace', '')[:500]}
URL: {event.get('page_url', 'N/A')}
Действие: {event.get('action', 'N/A')}
    """.strip()

    prompt = f"""
Проанализируй ошибку и ответь строго в формате JSON без пояснений:

{{
  "severity": "незначительно|низкая|средняя|высокая|критическая",
  "criticality": "можно не исправлять|не критично|требует внимания|блокирует функционал|авария",
  "recommendation": "Напиши также что сломалось(1-2 предложения). Краткая рекомендация для разработчика (1-2 предложения, на русском языке)"
}}

Описание ошибки:
{error_summary}
"""

    try:
        access_token = auth.get_access_token()
        
        proxies = {
            "http": os.getenv("HTTP_PROXY", ""),
            "https": os.getenv("HTTPS_PROXY", "")
        }
        proxies = {k: v for k, v in proxies.items() if v}
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "GigaChat-2-Pro",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500
        }

        response = requests.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions", 
            json=payload,
            headers=headers,
            proxies=proxies,
            verify=False,
            timeout=15
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]

        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError("Не удалось извлечь JSON")

    except Exception as e:
        return {
            "severity": "средняя",
            "criticality": "требует внимания",
            "recommendation": f"Ошибка ИИ: {str(e)[:100]}"
        }