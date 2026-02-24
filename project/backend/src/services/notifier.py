import os
from aiogram import Bot
from aiogram.types import FSInputFile 
from src.services.classifier import analyze_error_with_gigachat
import json
import re
import time

ts = str(int(time.time())) 

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_telegram_message(event: dict):
    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", str(event.get("user_id", "anonymous"))[:20])
    analysis = analyze_error_with_gigachat(event)
    
    context = event.get("context", {})
    metadata = event.get("metadata", {})
    
    platform = context.get("platform", "unknown")
    platform_emoji = {
        "frontend": "🖥️",
        "backend": "⚙️",
        "database": "🗃️"
    }.get(platform, "❓")

    short_meta = (
        f"Браузер: {context.get('browser', '—')} {context.get('browser_version', '')}\n"
        f"ОС: {context.get('os', '—')}\n"
        f"Тип: {event.get('action', 'N/A')}"
    )

    message = (
        f"{platform_emoji} <b>{platform.upper()} СЛОМАЛСЯ</b>\n\n"
        f"👤 Пользователь: <code>{event.get('user_id', 'anonymous')}</code>\n"
        f"🖱 Действие: {event.get('action', 'N/A')}\n"
        f"🌐 Страница: {event.get('page_url', 'N/A')}\n\n"
        f"<b>Метаданные:</b>\n{short_meta}\n\n"
        f"❗ <b>Срочность:</b> {analysis['severity']}\n"
        f"🔥 <b>Критичность:</b> {analysis['criticality']}\n"
        f"💡 <b>Рекомендация:</b> {analysis['recommendation']}"
    )

    full_info = json.dumps(event, indent=2, ensure_ascii=False)
    file_path = f"/tmp/error_{safe_user}_{ts}.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_info)

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
        parse_mode="HTML"
    )
    document = FSInputFile(file_path)
    await bot.send_document(
        chat_id=TELEGRAM_CHAT_ID,
        document=document,
        caption="📄 Полная информация об ошибке"
    )