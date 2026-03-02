import os
import asyncio
import json
import re
import time
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from src.core.models import ErrorTask, Event, ErrorGroup
from src.services.classifier import analyze_error_with_gigachat
import uuid

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Настройка движка для работы с БД
DATABASE_URL = "postgresql://postgres:postgres@db:5432/Monitoring"
engine = create_engine(DATABASE_URL)

# Конфигурация троттлинга (в секундах)
THROTTLE_CONFIG = {
    "низкая": 3600,        # 1 час
    "средняя": 1800,        # 30 минут
    "высокая": 900,         # 15 минут
    "критическая": 300      # 5 минут
}

def get_platform_emoji(platform: str) -> str:
    """Возвращает эмодзи для платформы"""
    emoji_map = {
        "frontend": "🖥️",
        "backend": "⚙️",
        "database": "🗃️",
        "mobile": "📱",
        "desktop": "💻",
        "browser": "🌐",
        "server": "🖧",
        "python": "🐍",
        "javascript": "📜",
        "node": "🟢",
        "django": "🎸",
        "fastapi": "⚡",
        "flask": "🍶"
    }
    return emoji_map.get(platform.lower(), "❓")

def get_severity_emoji(severity: str) -> str:
    """Возвращает эмодзи для уровня срочности"""
    emoji_map = {
        "низкая": "🟢",
        "средняя": "🟡",
        "высокая": "🟠",
        "критическая": "🔴"
    }
    return emoji_map.get(severity.lower(), "⚪")

def get_criticality_emoji(criticality: str) -> str:
    """Возвращает эмодзи для критичности"""
    emoji_map = {
        "не требует внимания": "✅",
        "требует внимания": "⚠️",
        "критично": "🔥"
    }
    return emoji_map.get(criticality.lower(), "❓")

def format_context(context_data: dict) -> str:
    """Форматирует контекст для отображения"""
    parts = []
    
    if context_data.get("platform"):
        parts.append(f"📱 Платформа: {context_data['platform']}")
    if context_data.get("language"):
        parts.append(f"💻 Язык: {context_data['language']}")
    if context_data.get("os_family"):
        parts.append(f"⚙️ ОС: {context_data['os_family']}")
    if context_data.get("browser_family"):
        browser = context_data['browser_family']
        if context_data.get("browser_version"):
            browser += f" {context_data['browser_version']}"
        parts.append(f"🌐 Браузер: {browser}")
    
    return "\n".join(parts) if parts else "—"

def format_metadata(metadata: dict) -> str:
    """Форматирует метаданные для отображения"""
    parts = []
    
    important_fields = [
        ("method", "📡 Метод"),
        ("endpoint", "🔗 Эндпоинт"),
        ("status_code", "📊 Статус"),
        ("duration_ms", "⏱️ Время (мс)"),
        ("remote_ip", "🌍 IP"),
        ("user_agent", "🖥️ User-Agent"),
        ("exception_type", "❌ Тип ошибки"),
        ("error_message", "📝 Сообщение"),
        ("path", "📁 Путь"),
        ("query_string", "🔍 Параметры"),
    ]
    
    for field, label in important_fields:
        if field in metadata and metadata[field]:
            value = metadata[field]
            if field == "duration_ms" and isinstance(value, (int, float)):
                value = f"{value:.0f}"
            parts.append(f"{label}: {value}")
    
    if "traceback" in metadata and metadata["traceback"]:
        trace = metadata["traceback"][:200] + "..." if len(metadata["traceback"]) > 200 else metadata["traceback"]
        parts.append(f"\n📚 Stacktrace:\n<code>{trace}</code>")
    
    return "\n".join(parts) if parts else "—"

def should_send_notification(db: Session, error_group_id: uuid.UUID, severity: str,  status_code: int = None) -> bool:
    """
    Проверяет, нужно ли отправлять уведомление на основе троттлинга
    Возвращает True если:
    1. Это первое уведомление для группы
    2. Прошло достаточно времени с последнего
    3. Severity повысился
    """

    if status_code == 404:
        task = db.query(ErrorTask).filter(
            ErrorTask.error_group_id == error_group_id
        ).first()
        
        if task:
            logger.info(f"ℹ️ 404 error already reported for group {error_group_id}, skipping")
            return False
        return True

    throttle_time = THROTTLE_CONFIG.get(severity, 1800)  # По умолчанию 30 минут
    
    # Ищем последнюю задачу для этой группы ошибок
    task = db.query(ErrorTask).filter(
        ErrorTask.error_group_id == error_group_id
    ).order_by(ErrorTask.created_at.desc()).first()
    
    if not task:
        logger.info(f"📨 First notification for group {error_group_id}")
        return True  # Никогда не отправляли - можно отправлять
    
    if task.last_notification_sent_at:
        # Проверяем, прошло ли достаточно времени
        time_since_last = datetime.utcnow() - task.last_notification_sent_at.replace(tzinfo=None)
        
        # Если severity повысился (например, была "средняя", стала "критическая")
        # то отправляем сразу, игнорируя троттлинг
        if task.last_severity != severity:
            logger.info(f"⚠️ Severity changed from {task.last_severity} to {severity}, sending immediately")
            return True
        
        if time_since_last.total_seconds() < throttle_time:
            logger.info(f"⏱️ Throttling notification for group {error_group_id}. "
                       f"Last sent {time_since_last.total_seconds():.0f}s ago, "
                       f"need {throttle_time}s")
            return False
    
    return True

def create_error_task(db: Session, event_id: uuid.UUID, error_group_id: uuid.UUID, 
                     project_id: uuid.UUID) -> ErrorTask:
    """Создаёт запись о задаче в БД"""
    task = ErrorTask(
        event_id=event_id,
        error_group_id=error_group_id,
        project_id=project_id
    )
    db.add(task)
    db.flush()
    return task

def update_task_notification(db: Session, task_id: uuid.UUID, 
                           telegram_message_id: int, telegram_chat_id: str,
                           severity: str):
    """Обновляет информацию об отправленном уведомлении"""
    task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
    if task:
        task.last_notification_sent_at = datetime.utcnow()
        task.notification_count += 1
        task.telegram_message_id = telegram_message_id
        task.telegram_chat_id = telegram_chat_id
        task.last_severity = severity  # Сохраняем severity
        db.commit()

def get_task_status_emoji(task: ErrorTask) -> str:
    """Возвращает эмодзи статуса задачи"""
    if task.is_resolved:
        return "✅"
    elif task.is_acknowledged:
        return "🔄"
    else:
        return "⏳"

def get_task_status_text(task: ErrorTask) -> str:
    """Возвращает текст статуса задачи"""
    if task.is_resolved:
        return "Решена"
    elif task.is_acknowledged:
        return "В работе"
    else:
        return "Ожидает"

def create_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопками для задачи"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="▶️ Начать работу", 
                callback_data=f"ack_{task_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Отметить решённой", 
                callback_data=f"resolve_{task_id}"
            )
        ]
    ])
    return keyboard

def create_resolved_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру для решённой задачи"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Задача выполнена", 
                callback_data="resolved",
                disabled=True
            )
        ]
    ])
    return keyboard

async def send_telegram_message_async(event: dict, error_group_id: uuid.UUID, task_id: uuid.UUID = None):
    """
    Асинхронная отправка уведомления об ошибке в Telegram с кнопками
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    ts = str(int(time.time()))
    
    try:
        # Безопасное имя файла
        safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", str(event.get("meta", {}).get("user_id", "anonymous"))[:20])
        
        # Анализируем через GigaChat
        analysis = analyze_error_with_gigachat(event)
        
        # Извлекаем данные
        context = event.get("context", {})
        meta = event.get("meta", {})
        
        # Определяем платформу
        platform = context.get("platform", "unknown")
        platform_emoji = get_platform_emoji(platform)
        
        # Определяем severity и criticality
        severity = analysis.get("severity", "средняя")
        criticality = analysis.get("criticality", "требует внимания")
        severity_emoji = get_severity_emoji(severity)
        criticality_emoji = get_criticality_emoji(criticality)
        
        # Форматируем контекст и метаданные
        context_text = format_context(context)
        meta_text = format_metadata(meta)
        
        # Получаем action из события
        action = event.get("action", "N/A")
        
        # Получаем статус задачи, если есть task_id
        status_emoji = "⏳"
        status_text = "Ожидает"
        
        if task_id:
            db = Session(engine)
            try:
                task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
                if task:
                    status_emoji = get_task_status_emoji(task)
                    status_text = get_task_status_text(task)
                    task_display_id = str(task_id)
            finally:
                db.close()
        
        # Формируем заголовок
        if "exception" in action:
            title = f"{platform_emoji} <b>❌ ИСКЛЮЧЕНИЕ: {action.replace('exception:', '').strip()}</b>"
        else:
            title = f"{platform_emoji} <b>{platform.upper()} СОБЫТИЕ</b>"
        
        # Основное сообщение
        message_parts = [
            title,
            "",
            f"🆔 <b>ID задачи:</b> <code>{task_display_id}</code>",
            f"👤 <b>Пользователь:</b> <code>{meta.get('user_id', 'anonymous')}</code>",
            f"🖱 <b>Действие:</b> <code>{action}</code>",
            f"🌐 <b>Страница:</b> {meta.get('page_url', 'N/A')}",
            "",
            f"<b>📊 Контекст:</b>",
            f"{context_text}",
            "",
            f"<b>📋 Детали:</b>",
            f"{meta_text}",
            "",
            f"<b>🔍 Анализ GigaChat:</b>",
            f"{severity_emoji} <b>Срочность:</b> {severity.upper()}",
            f"{criticality_emoji} <b>Критичность:</b> {criticality.upper()}",
            f"💡 <b>Рекомендация:</b> {analysis.get('recommendation', '—')}",
            "",
            f"<b>📌 Статус:</b> {status_emoji} {status_text}"
        ]
        
        message = "\n".join(message_parts)
        
        # Сохраняем полную информацию в файл
        full_info = json.dumps(event, indent=2, ensure_ascii=False)
        file_path = f"/tmp/error_{safe_user}_{ts}.txt"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_info)
        
        # Создаём клавиатуру
        if task_id:
            if status_text == "Решена":
                keyboard = create_resolved_keyboard()
            else:
                keyboard = create_task_keyboard(str(task_id))
        else:
            keyboard = None
        
        # Отправляем сообщение
        sent_message = await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Отправляем файл с полной информацией
        document = FSInputFile(file_path)
        await bot.send_document(
            chat_id=TELEGRAM_CHAT_ID,
            document=document,
            caption="📄 Полная информация об ошибке"
        )
        
        logger.info(f"✅ Telegram notification sent for event: {action}")
        
        return sent_message.message_id
        
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram message: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()

async def update_telegram_message(task_id: uuid.UUID):
    """
    Обновляет сообщение в Telegram при изменении статуса задачи
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        db = Session(engine)
        try:
            # Получаем задачу
            task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
            if not task or not task.telegram_message_id:
                logger.warning(f"Task {task_id} not found or no message_id")
                return
            
            # Получаем событие и группу
            event = db.query(Event).filter(Event.id == task.event_id).first()
            error_group = db.query(ErrorGroup).filter(ErrorGroup.id == task.error_group_id).first()
            
            if not event or not error_group:
                logger.warning(f"Event or error group not found for task {task_id}")
                return
            
            # Получаем текущий статус
            status_emoji = get_task_status_emoji(task)
            status_text = get_task_status_text(task)
            
            # Сначала получаем текущее сообщение, чтобы не потерять контент
            try:
                # Пытаемся получить сообщение (но мы не можем его получить через API бота,
                # поэтому просто обновляем статус в существующем сообщении)
                
                # Создаём новую клавиатуру
                if task.is_resolved:
                    keyboard = create_resolved_keyboard()
                else:
                    keyboard = create_task_keyboard(str(task_id))
                
                # Обновляем сообщение - меняем только клавиатуру и строку статуса
                # В реальности нужно хранить полный текст сообщения или получать его
                # Но для простоты отправим новое сообщение с обновлённым статусом
                
                # Получаем текст сообщения (в идеале нужно хранить его в БД)
                # Пока просто отправляем уведомление о изменении статуса отдельно
                
                # Отправляем новое сообщение с обновлённым статусом
                await bot.send_message(
                    chat_id=task.telegram_chat_id,
                    text=f"🔄 Статус задачи изменён: {status_emoji} {status_text}",
                    parse_mode="HTML"
                )
                
                # Обновляем исходное сообщение - меняем клавиатуру
                await bot.edit_message_reply_markup(
                    chat_id=task.telegram_chat_id,
                    message_id=task.telegram_message_id,
                    reply_markup=keyboard
                )
                
                logger.info(f"✅ Updated telegram message for task {task_id}")
                
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    logger.error(f"❌ Failed to update telegram message: {e}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Failed to update telegram message: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()

def send_telegram_message_sync(event: dict, error_group_id: uuid.UUID, task_id: uuid.UUID = None):
    """
    Синхронная обёртка для отправки уведомления в Telegram.
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message_id = loop.run_until_complete(
            send_telegram_message_async(event, error_group_id, task_id)
        )
        logger.info("✅ Telegram notification sent successfully")
        return message_id
    except Exception as e:
        logger.error(f"❌ Failed to send telegram message: {e}", exc_info=True)
        return None
    finally:
        if loop:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

def update_telegram_message_sync(task_id: uuid.UUID):
    """
    Синхронная обёртка для обновления сообщения в Telegram
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update_telegram_message(task_id))
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update telegram message: {e}", exc_info=True)
        return False
    finally:
        if loop:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

__all__ = [
    'send_telegram_message_sync',
    'update_telegram_message_sync',
    'should_send_notification',
    'create_error_task',
    'update_task_notification',
    'TELEGRAM_CHAT_ID'  # Добавьте эту строку
]