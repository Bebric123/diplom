# backend/src/services/notifier.py
import os
from aiogram import Bot

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_telegram_message(text: str):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")