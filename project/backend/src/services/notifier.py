import asyncio
import json
import logging
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from src.core.config import get_settings
from src.core.database import SessionLocal
from src.core.models import ErrorGroup, ErrorTask, Event, EventContext, Project
from src.services.classifier import analyze_error_with_gigachat

logger = logging.getLogger(__name__)


def _bot_token() -> str:
    return get_settings().telegram_bot_token


def _telegram_chat_id_for_api(chat_id: str):
    """
    Telegram Bot API для числовых чатов ожидает целое (супергруппа −100…, группа −…).
    Строка с пробелами или неверный формат — источник «chat not found».
    """
    s = str(chat_id).strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,20}", s):
        return int(s)
    return s


def get_project_telegram_chat_id(db: Session, project_id: uuid.UUID) -> Optional[str]:
    """Chat id для алертов по проекту (из регистрации). Без него уведомления не отправляются."""
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or not p.telegram_chat_id:
        return None
    s = str(p.telegram_chat_id).strip()
    return s or None

# Троттлинг алертов по нормализованной severity (секунды между повторами для той же группы)
THROTTLE_CONFIG = {
    "низкая": 3600,
    "средняя": 1800,
    "высокая": 900,
    "критическая": 300,
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


def _event_to_analyzer_payload(event: Event) -> dict:
    meta = dict(event.metadata_ or {})
    page_url = meta.get("page_url", "N/A")
    if event.context:
        ctx = event.context
        platform_name = ctx.platform.name if ctx.platform else "unknown"
        context_data = {
            "platform": platform_name,
            "language": ctx.language or "javascript",
            "os_family": ctx.os_family or "unknown",
            "browser_family": ctx.browser_family or "unknown",
        }
        if ctx.browser_version:
            context_data["browser_version"] = ctx.browser_version
    else:
        context_data = {
            "platform": "unknown",
            "language": "javascript",
            "os_family": "unknown",
            "browser_family": "unknown",
        }
    return {
        "context": context_data,
        "meta": meta,
        "action": event.action,
        "page_url": page_url,
    }


def should_send_notification(
    db: Session, error_group_id: uuid.UUID, severity: str, status_code: Optional[int] = None
) -> bool:
    """
    Дедупликация алертов по группе (error_group_id) + троттлинг по времени и severity.

    - Первая отправка по группе (alert_last_sent_at is None) → отправить.
    - Смена severity → отправить сразу (новый класс риска).
    - Тот же severity и интервал < THROTTLE_CONFIG → не отправлять.
    - 404: не слать повторно, если по группе уже есть задача (уже уведомляли).
    """
    group = db.query(ErrorGroup).filter(ErrorGroup.id == error_group_id).first()
    if not group:
        return True

    if status_code == 404:
        if db.query(ErrorTask.id).filter(ErrorTask.error_group_id == error_group_id).first():
            logger.info("404 already reported for group %s, skipping", error_group_id)
            return False
        return True

    sev = (severity or "средняя").strip().lower()
    throttle_time = THROTTLE_CONFIG.get(sev, 1800)

    if group.alert_last_sent_at is None:
        logger.info("First alert for group %s", error_group_id)
        return True

    last_sev = (group.alert_last_severity or "").lower()
    if last_sev != sev:
        logger.info("Severity changed %s -> %s, send alert", last_sev, sev)
        return True

    now = datetime.now(timezone.utc)
    last_at = group.alert_last_sent_at
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    elapsed = (now - last_at).total_seconds()
    if elapsed < throttle_time:
        logger.info(
            "Throttling group %s: %.0fs < %ss (severity=%s)",
            error_group_id,
            elapsed,
            throttle_time,
            sev,
        )
        return False
    return True


def _pg_advisory_keys(error_group_id: uuid.UUID) -> tuple[int, int]:
    """Два int для pg_advisory_lock (стабильно по UUID группы)."""
    b = error_group_id.bytes
    k1 = int.from_bytes(b[:4], "big") & 0x7FFFFFFF
    k2 = int.from_bytes(b[4:8], "big") & 0x7FFFFFFF
    return k1, k2


def advisory_lock_notify_group(db: Session, error_group_id: uuid.UUID) -> None:
    """
    Сериализация алертов по одной группе между воркерами Celery.
    Без этого несколько воркеров могут одновременно пройти should_send_notification
    до обновления alert_last_sent_at и отправить пачку дублей в Telegram.
    """
    k1, k2 = _pg_advisory_keys(error_group_id)
    db.execute(text("SELECT pg_advisory_lock(CAST(:k1 AS int), CAST(:k2 AS int))"), {"k1": k1, "k2": k2})


def advisory_unlock_notify_group(db: Session, error_group_id: uuid.UUID) -> None:
    k1, k2 = _pg_advisory_keys(error_group_id)
    db.execute(text("SELECT pg_advisory_unlock(CAST(:k1 AS int), CAST(:k2 AS int))"), {"k1": k1, "k2": k2})


def update_error_group_alert_anchor(
    db: Session, error_group_id: uuid.UUID, severity: str
) -> None:
    """Фиксирует время/severity последнего алерта по группе (события и логи)."""
    g = db.query(ErrorGroup).filter(ErrorGroup.id == error_group_id).first()
    if g:
        g.alert_last_sent_at = datetime.now(timezone.utc)
        g.alert_last_severity = (severity or "средняя").strip().lower()

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
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        if task:
            # Явно загружаем все нужные атрибуты
            _ = task.id  # принудительно загружаем
            task.last_notification_sent_at = datetime.now(timezone.utc)
            task.notification_count += 1
            task.telegram_message_id = telegram_message_id
            task.telegram_chat_id = telegram_chat_id
            task.last_severity = severity
            grp = db.query(ErrorGroup).filter(ErrorGroup.id == task.error_group_id).first()
            if grp:
                grp.alert_last_sent_at = task.last_notification_sent_at
                grp.alert_last_severity = (severity or "средняя").strip().lower()
            db.commit()
            logger.debug(f"Task {task_id} notification updated")
    except Exception as e:
        logger.error(f"Error updating task notification: {e}")
        db.rollback()

def get_task_status_emoji(task: ErrorTask) -> str:
    if not task:
        return "❔"
    if task.is_resolved:
        return "✅"
    elif task.is_acknowledged:
        return "🔄"
    else:
        return "⏳"

def get_task_status_text(task: ErrorTask) -> str:
    if not task:
        return "Не создана"
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

def build_message(event: dict, task: ErrorTask, analysis: dict) -> str:
    context = event.get("context", {})
    meta = event.get("meta", {})
    action = event.get("action", "N/A")

    platform = context.get("platform", "unknown")
    platform_emoji = get_platform_emoji(platform)

    severity = analysis.get("severity", "средняя")
    criticality = analysis.get("criticality", "требует внимания")

    severity_emoji = get_severity_emoji(severity)
    criticality_emoji = get_criticality_emoji(criticality)

    context_text = format_context(context)
    meta_text = format_metadata(meta)

    status_emoji = get_task_status_emoji(task)
    status_text = get_task_status_text(task)

    if "exception" in action:
        title = f"{platform_emoji} <b>❌ ИСКЛЮЧЕНИЕ: {action.replace('exception:', '').strip()}</b>"
    else:
        title = f"{platform_emoji} <b>{platform.upper()} СОБЫТИЕ</b>"

    message = "\n".join([
        title,
        "",
        # f"🆔 <b>ID задачи:</b> <code>{task.id}</code>",
        f"👤 <b>Пользователь:</b> <code>{meta.get('user_id', 'anonymous')}</code>",
        f"🖱 <b>Действие:</b> <code>{action}</code>",
        f"🌐 <b>Страница:</b> {meta.get('page_url', 'N/A')}",
        "",
        f"<b>📊 Контекст:</b>",
        context_text,
        "",
        f"<b>📋 Детали:</b>",
        meta_text,
        "",
        f"<b>🔍 Анализ:</b>",
        f"{severity_emoji} <b>Срочность:</b> {severity.upper()}",
        f"{criticality_emoji} <b>Критичность:</b> {criticality.upper()}",
        f"💡 <b>Рекомендация:</b> {analysis.get('recommendation', '—')}",
        "",
        f"<b>📌 Статус:</b> {status_emoji} {status_text}",
        # f"🔁 <b>Обновлений:</b> {task.notification_count}"
    ])

    return message

async def send_telegram_message_async(
    event: dict,
    error_group_id: uuid.UUID,
    task_id: Optional[uuid.UUID] = None,
    telegram_chat_id: Optional[str] = None,
):
    """
    Асинхронная отправка уведомления об ошибке в Telegram с кнопками.
    telegram_chat_id — чат проекта; без него отправка пропускается.
    """
    if not telegram_chat_id or not str(telegram_chat_id).strip():
        logger.warning("Telegram: нет chat_id проекта, уведомление пропущено (group=%s)", error_group_id)
        return None

    chat_id = _telegram_chat_id_for_api(telegram_chat_id)
    bot = Bot(token=_bot_token())
    ts = str(int(time.time()))
    file_path: Optional[str] = None

    try:
        # Безопасное имя файла
        safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", str(event.get("meta", {}).get("user_id", "anonymous"))[:20])
        
        # Анализируем через GigaChat
        analysis = analyze_error_with_gigachat(event)

        db = SessionLocal()
        try:
            task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
        finally:
            db.close()

        status_text = get_task_status_text(task)

        message = build_message(event, task, analysis)

        full_info = json.dumps(event, indent=2, ensure_ascii=False)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            prefix=f"errmon_{safe_user}_{ts}_",
            suffix=".txt",
        )
        try:
            tmp.write(full_info)
            tmp.close()
            file_path = tmp.name
        except Exception:
            tmp.close()
            raise

        if task_id:
            if status_text == "Решена":
                keyboard = create_resolved_keyboard()
            else:
                keyboard = create_task_keyboard(str(task_id))
        else:
            keyboard = None

        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        # Документ отдельно: при FloodWait/429 текст уже ушёл — не теряем message_id и якорь троттлинга
        if file_path and os.path.isfile(file_path):
            try:
                document = FSInputFile(file_path)
                await bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    caption="📄 Полная информация об ошибке",
                )
            except Exception as doc_err:
                logger.warning(
                    "Telegram send_document failed (краткое сообщение уже доставлено): %s",
                    doc_err,
                    exc_info=True,
                )

        return sent_message.message_id

    except Exception as e:
        logger.error(f"❌ Failed to send Telegram message: {e}", exc_info=True)
        raise
    finally:
        if file_path and os.path.isfile(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass
        await bot.session.close()

async def update_telegram_message(task_id: uuid.UUID):
    bot = Bot(token=_bot_token())

    try:
        db = SessionLocal()
        try:
            task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()
            if not task or not task.telegram_message_id:
                logger.warning("Task %s not found or no message_id", task_id)
                return

            event = (
                db.query(Event)
                .options(joinedload(Event.context).joinedload(EventContext.platform))
                .filter(Event.id == task.event_id)
                .first()
            )
            error_group = db.query(ErrorGroup).filter(ErrorGroup.id == task.error_group_id).first()

            if not event or not error_group:
                logger.warning("Event or error group not found for task %s", task_id)
                return

            event_dict = _event_to_analyzer_payload(event)
            analysis = analyze_error_with_gigachat(event_dict)
            updated_message = build_message(event_dict, task, analysis)

            if task.is_resolved:
                keyboard = create_resolved_keyboard()
            else:
                keyboard = create_task_keyboard(str(task_id))

            try:
                await bot.edit_message_text(
                    chat_id=_telegram_chat_id_for_api(task.telegram_chat_id),
                    message_id=task.telegram_message_id,
                    text=updated_message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                logger.info("Message updated for task %s", task_id)
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    logger.error("Telegram update error: %s", e)
        finally:
            db.close()
    except Exception as e:
        logger.error("Failed to update telegram message: %s", e, exc_info=True)
        raise
    finally:
        await bot.session.close()

def send_telegram_message_sync(
    event: dict,
    error_group_id: uuid.UUID,
    task_id: Optional[uuid.UUID] = None,
    telegram_chat_id: Optional[str] = None,
):
    """
    Синхронная обёртка для отправки уведомления в Telegram.
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message_id = loop.run_until_complete(
            send_telegram_message_async(
                event, error_group_id, task_id, telegram_chat_id=telegram_chat_id
            )
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
    "advisory_lock_notify_group",
    "advisory_unlock_notify_group",
    "send_telegram_message_async",
    "send_telegram_message_sync",
    "update_telegram_message",
    "update_telegram_message_sync",
    "should_send_notification",
    "update_error_group_alert_anchor",
    "create_error_task",
    "update_task_notification",
    "get_project_telegram_chat_id",
]