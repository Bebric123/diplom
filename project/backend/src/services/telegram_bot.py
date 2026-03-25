import logging
import os
import uuid
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from sqlalchemy import func

from src.core.database import SessionLocal
from src.core.models import ErrorTask
from src.services.notifier import update_telegram_message

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def format_task_id(task_id: uuid.UUID) -> str:
    """Форматирует ID задачи для отображения"""
    full_id = str(task_id)
    short_id = full_id
    return f"<code>{short_id}</code>"

@dp.callback_query(lambda c: c.data and (c.data.startswith("ack_") or c.data.startswith("resolve_")))
async def process_callback(callback_query: types.CallbackQuery):
    """Обрабатывает нажатия на кнопки (callback_data: ack_<uuid> / resolve_<uuid>)."""
    data = callback_query.data or ""
    if data.startswith("ack_"):
        action = "ack"
        task_id_str = data[4:]
    elif data.startswith("resolve_"):
        action = "resolve"
        task_id_str = data[8:]
    else:
        await callback_query.answer("Неизвестная команда")
        return

    try:
        task_id = uuid.UUID(task_id_str)
    except ValueError:
        await callback_query.answer("Неверный ID задачи")
        return

    db = SessionLocal()
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        
        if not task:
            await callback_query.answer("Задача не найдена")
            return

        formatted_id = format_task_id(task_id)

        if action == "ack":
            if task.is_resolved:
                await callback_query.answer(f"Задача {formatted_id} уже решена", show_alert=False)
                return

            task.is_acknowledged = True
            task.acknowledged_at = datetime.now(timezone.utc)
            db.commit()

            await callback_query.answer(f"Задача {formatted_id} взята в работу", show_alert=False)

        elif action == "resolve":
            if task.is_resolved:
                await callback_query.answer(f"Задача {formatted_id} уже решена", show_alert=False)
                return

            task.is_resolved = True
            task.resolved_at = datetime.now(timezone.utc)
            db.commit()

            await callback_query.answer(f"Задача {formatted_id} отмечена как решённая", show_alert=False)
        
        # Обновляем сообщение в Telegram
        await update_telegram_message(task_id)
        
    except Exception as e:
        logger.error("Error processing callback: %s", e, exc_info=True)
        await callback_query.answer("Произошла ошибка при обработке запроса", show_alert=True)
    finally:
        db.close()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветственное сообщение"""
    await message.answer(
        "👋 <b>Привет! Я бот для мониторинга ошибок</b>\n\n"
        "📋 <b>Мои возможности:</b>\n"
        "• Отправка уведомлений об ошибках\n"
        "• Отслеживание статуса задач\n"
        "• Кнопки для управления задачами\n\n"
        "🆔 <b>ID задач</b> будут отображаться в формате: <code>550e8400</code>\n\n"
        "Нажми на кнопку под сообщением об ошибке, чтобы начать работу или отметить задачу как решённую.",
        parse_mode="HTML"
    )

@dp.message(Command("task"))
async def cmd_task(message: types.Message):
    """Показывает информацию о задаче по ID"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Укажите ID задачи.\n"
            "Пример: <code>/task 550e8400-e29b-41d4-a716-446655440000</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        task_id = uuid.UUID(args[1])
    except ValueError:
        await message.answer("❌ Неверный формат ID задачи")
        return
    
    db = SessionLocal()
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        
        if not task:
            await message.answer(f"❌ Задача с ID <code>{args[1][:8]}</code> не найдена", parse_mode="HTML")
            return
        
        if task.is_resolved:
            status = "✅ РЕШЕНА"
        elif task.is_acknowledged:
            status = "🔄 В РАБОТЕ"
        else:
            status = "⏳ ОЖИДАЕТ"

        response = (
            f"📋 <b>Информация о задаче</b>\n\n"
            f"🆔 <b>ID:</b> <code>{task_id}</code>\n"
            f"📌 <b>Статус:</b> {status}\n"
            f"📊 <b>Уведомлений:</b> {task.notification_count}\n"
            f"📅 <b>Создана:</b> {task.created_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        )
        
        if task.acknowledged_at:
            response += f"▶️ <b>Взята в работу:</b> {task.acknowledged_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        if task.resolved_at:
            response += f"✅ <b>Решена:</b> {task.resolved_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        if task.last_notification_sent_at:
            response += f"📨 <b>Последнее уведомление:</b> {task.last_notification_sent_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        await message.answer(response, parse_mode="HTML")
        
    finally:
        db.close()

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику по задачам"""
    db = SessionLocal()
    try:
        total = db.query(ErrorTask).count()
        resolved = db.query(ErrorTask).filter(ErrorTask.is_resolved.is_(True)).count()
        in_progress = db.query(ErrorTask).filter(
            ErrorTask.is_acknowledged.is_(True),
            ErrorTask.is_resolved.is_(False),
        ).count()
        waiting = db.query(ErrorTask).filter(
            ErrorTask.is_acknowledged.is_(False),
            ErrorTask.is_resolved.is_(False),
        ).count()

        avg_time = db.query(
            func.avg(
                func.extract('epoch', ErrorTask.resolved_at - ErrorTask.created_at)
            )
        ).filter(ErrorTask.resolved_at.isnot(None)).scalar()
        
        avg_time_str = f"{avg_time/60:.1f} минут" if avg_time else "—"
        
        response = (
            f"📊 <b>Статистика задач</b>\n\n"
            f"📌 <b>Всего задач:</b> {total}\n"
            f"✅ <b>Решено:</b> {resolved}\n"
            f"🔄 <b>В работе:</b> {in_progress}\n"
            f"⏳ <b>Ожидают:</b> {waiting}\n"
            f"⏱️ <b>Среднее время решения:</b> {avg_time_str}\n"
        )
        
        await message.answer(response, parse_mode="HTML")
        
    finally:
        db.close()

async def main():
    """Запуск бота"""
    logger.info("🚀 Telegram bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())