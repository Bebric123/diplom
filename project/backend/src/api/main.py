# backend/src/api/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.src.services.notifier import send_telegram_message
import logging
import backend.src.core

app = FastAPI(title="User Action Monitor")

class UserAction(BaseModel):
    user_id: str
    action: str
    page_url: str = ""
    metadata: dict = {}

@app.post("/track")
async def track_action(action: UserAction):
    try:
        message = (
            f"👤 Пользователь: `{action.user_id}`\n"
            f"🖱 Действие: `{action.action}`\n"
            f"🌐 Страница: {action.page_url}\n"
            f"📦 Метаданные: {action.metadata}"
        )
        await send_telegram_message(message)
        logging.info(f"Tracked: {action.user_id} — {action.action}")
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Failed to send: {e}")
        raise HTTPException(status_code=500, detail="Failed to notify")