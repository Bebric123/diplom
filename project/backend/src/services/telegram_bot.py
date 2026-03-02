import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from datetime import datetime
import uuid

from src.core.models import ErrorTask
from src.services.notifier import update_telegram_message

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = "postgresql://postgres:postgres@db:5432/Monitoring"
engine = create_engine(DATABASE_URL)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def format_task_id(task_id: uuid.UUID) -> str:
    """Форматирует ID задачи для отображения"""
    full_id = str(task_id)
    short_id = full_id
    return f"<code>{short_id}</code>"

@dp.callback_query(lambda c: c.data and c.data.startswith(('ack_', 'resolve_')))
async def process_callback(callback_query: types.CallbackQuery):
    """Обрабатывает нажатия на кнопки"""
    action, task_id_str = callback_query.data.split('_', 1)
    
    try:
        task_id = uuid.UUID(task_id_str)
    except ValueError:
        await callback_query.answer("❌ Неверный ID задачи")
        return
    
    db = Session(engine)
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        
        if not task:
            await callback_query.answer("❌ Задача не найдена")
            return
        
        formatted_id = format_task_id(task_id)
        
        if action == 'ack':
            if task.is_resolved:
                await callback_query.answer(
                    f"❌ Задача {formatted_id} уже решена",
                    show_alert=False
                )
                return
            
            task.is_acknowledged = True
            task.acknowledged_at = datetime.utcnow()
            db.commit()
            
            await callback_query.answer(
                f"✅ Задача {formatted_id} взята в работу",
                show_alert=False
            )
            
        elif action == 'resolve':
            if task.is_resolved:
                await callback_query.answer(
                    f"❌ Задача {formatted_id} уже решена",
                    show_alert=False
                )
                return
            
            task.is_resolved = True
            task.resolved_at = datetime.utcnow()
            db.commit()
            
            await callback_query.answer(
                f"✅ Задача {formatted_id} отмечена как решённая",
                show_alert=False
            )
        
        # Обновляем сообщение в Telegram
        await update_telegram_message(task_id)
        
        # Отправляем отдельное сообщение с подтверждением (опционально)
        status = "✅ РЕШЕНА" if task.is_resolved else "🔄 В РАБОТЕ"
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=(
                f"🔄 <b>Статус задачи обновлён</b>\n\n"
                f"🆔 ID задачи: {formatted_id}\n"
                f"📌 Новый статус: {status}\n"
                f"👤 Пользователь: @{callback_query.from_user.username or 'anonymous'}"
            ),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error processing callback: {e}", exc_info=True)
        await callback_query.answer(
            "❌ Произошла ошибка при обработке запроса",
            show_alert=True
        )
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
    
    db = Session(engine)
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        
        if not task:
            await message.answer(f"❌ Задача с ID <code>{args[1][:8]}</code> не найдена", parse_mode="HTML")
            return
        
        # Получаем статус
        if task.is_resolved:
            status = "✅ РЕШЕНА"
            status_time = task.resolved_at
        elif task.is_acknowledged:
            status = "🔄 В РАБОТЕ"
            status_time = task.acknowledged_at
        else:
            status = "⏳ ОЖИДАЕТ"
            status_time = None
        
        # Формируем ответ
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
    db = Session(engine)
    try:
        # Получаем статистику
        total = db.query(ErrorTask).count()
        resolved = db.query(ErrorTask).filter(ErrorTask.is_resolved == True).count()
        in_progress = db.query(ErrorTask).filter(
            ErrorTask.is_acknowledged == True, 
            ErrorTask.is_resolved == False
        ).count()
        waiting = db.query(ErrorTask).filter(
            ErrorTask.is_acknowledged == False,
            ErrorTask.is_resolved == False
        ).count()
        
        # Среднее время решения (для решённых задач)
        from sqlalchemy import func
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