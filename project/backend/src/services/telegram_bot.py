import logging
import os
import uuid
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy import func

from src.core.database import SessionLocal
from src.core.models import ErrorTask
from src.services.notifier import update_telegram_message
from src.services.stats_service import aggregate_metrics, build_excel_report, default_range_days
from src.services.telegram_chat_project import is_group_like_chat, project_for_telegram_chat

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

HELP_HTML = (
    "<b>Команды бота</b>\n\n"
    "/start — приветствие и кнопки\n"
    "/help — эта справка\n"
    "/stats — сводка по проекту (только в чате, указанном при /register)\n"
    "/report — Excel за 7 дней (там же)\n"
    "/task &lt;uuid&gt; — карточка задачи\n\n"
    "Под сообщениями об ошибках — кнопки «Взять в работу» / «Решена»."
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопки-ярлыки (работают в чате проекта; в личке /stats и /report всё равно без проекта)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats"),
                InlineKeyboardButton(text="📎 Отчёт Excel", callback_data="menu_report"),
            ],
            [InlineKeyboardButton(text="❓ Справка", callback_data="menu_help")],
        ]
    )


async def setup_bot_commands(bot: Bot) -> None:
    """Меню команд (подсказка в Telegram рядом со скрепкой)."""
    commands = [
        BotCommand(command="start", description="Начало и кнопки"),
        BotCommand(command="help", description="Справка по командам"),
        BotCommand(command="stats", description="Сводка по проекту (в чате проекта)"),
        BotCommand(command="report", description="Excel за 7 дней"),
        BotCommand(command="task", description="Задача по UUID"),
    ]
    await bot.set_my_commands(commands)


def _telegram_user_label(user: types.User) -> str:
    if user.username:
        return f"@{user.username}"
    name = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
    return name or str(user.id)


def format_task_id(task_id: uuid.UUID) -> str:
    """Форматирует ID задачи для отображения"""
    full_id = str(task_id)
    short_id = full_id
    return f"<code>{short_id}</code>"


async def _safe_callback_answer(
    callback_query: types.CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    """
    answerCallbackQuery нужно вызвать пока query жив (~до нескольких минут).
    Иначе Telegram: «query is too old». Сеть до api.telegram.org может быть недоступна
    (firewall, air-gap, DNS) — не роняем обработчик update.
    """
    try:
        await callback_query.answer(text=text, show_alert=show_alert)
    except TelegramNetworkError as e:
        logger.warning("Telegram API недоступен (answer не отправлен): %s", e)
        return
    except TelegramBadRequest as e:
        err = (getattr(e, "message", None) or str(e)).lower()
        if any(
            x in err
            for x in (
                "query is too old",
                "response timeout expired",
                "query id is invalid",
            )
        ):
            logger.warning("Callback query устарел, answer пропущен: %s", e)
            return
        raise


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
        await _safe_callback_answer(callback_query, "Неизвестная команда")
        return

    try:
        task_id = uuid.UUID(task_id_str)
    except ValueError:
        await _safe_callback_answer(callback_query, "Неверный ID задачи")
        return

    db = SessionLocal()
    try:
        task = db.query(ErrorTask).filter(ErrorTask.id == task_id).first()

        if not task:
            await _safe_callback_answer(callback_query, "Задача не найдена")
            return

        msg = callback_query.message
        if msg and msg.chat and is_group_like_chat(msg.chat.type):
            grp = project_for_telegram_chat(db, msg.chat.id)
            if grp and task.project_id != grp.id:
                await _safe_callback_answer(
                    callback_query,
                    "Эта кнопка относится к другому проекту",
                    show_alert=True,
                )
                return

        formatted_id = format_task_id(task_id)

        user = callback_query.from_user
        if user is None:
            await _safe_callback_answer(
                callback_query,
                "Не удалось определить пользователя Telegram",
            )
            return

        if action == "ack":
            if task.is_resolved:
                await _safe_callback_answer(
                    callback_query,
                    f"Задача {formatted_id} уже решена",
                    show_alert=False,
                )
                return
            if task.is_acknowledged:
                await _safe_callback_answer(
                    callback_query,
                    f"Задача {formatted_id} уже в работе",
                    show_alert=False,
                )
                return

            task.is_acknowledged = True
            task.acknowledged_at = datetime.now(timezone.utc)
            task.acknowledged_by_telegram_user_id = user.id
            task.acknowledged_by_label = _telegram_user_label(user)
            db.commit()

            # Сразу подтверждаем нажатие — до LLM в update_telegram_message (может быть долго)
            await _safe_callback_answer(
                callback_query,
                f"Задача {formatted_id} взята в работу",
                show_alert=False,
            )

        elif action == "resolve":
            if task.is_resolved:
                await _safe_callback_answer(
                    callback_query,
                    f"Задача {formatted_id} уже решена",
                    show_alert=False,
                )
                return
            if not task.is_acknowledged:
                await _safe_callback_answer(
                    callback_query,
                    "Сначала нажмите «Взять в работу»",
                    show_alert=True,
                )
                return

            task.is_resolved = True
            task.resolved_at = datetime.now(timezone.utc)
            task.resolved_by_telegram_user_id = user.id
            task.resolved_by_label = _telegram_user_label(user)
            db.commit()

            await _safe_callback_answer(
                callback_query,
                f"Задача {formatted_id} отмечена как решённая",
                show_alert=False,
            )

        # Без повторного LLM: иначе бот блокируется на минуты, callback протухает, кнопка не меняется
        try:
            await update_telegram_message(task_id, reanalyze=False)
        except TelegramNetworkError as net_err:
            logger.warning("Не удалось обновить сообщение в Telegram (сеть): %s", net_err)

    except Exception as e:
        logger.error("Error processing callback: %s", e, exc_info=True)
        await _safe_callback_answer(
            callback_query,
            "Произошла ошибка при обработке запроса",
            show_alert=True,
        )
    finally:
        db.close()


def _format_project_stats_lines(db, proj) -> list[str]:
    """Текст сводки /stats для проекта (общая логика с командой и callback)."""
    pid = proj.id
    base_task = db.query(ErrorTask).filter(ErrorTask.project_id == pid)
    total = base_task.count()
    resolved = base_task.filter(ErrorTask.is_resolved.is_(True)).count()
    in_progress = base_task.filter(
        ErrorTask.is_acknowledged.is_(True),
        ErrorTask.is_resolved.is_(False),
    ).count()
    waiting = base_task.filter(
        ErrorTask.is_acknowledged.is_(False),
        ErrorTask.is_resolved.is_(False),
    ).count()

    sec = func.extract("epoch", ErrorTask.resolved_at - ErrorTask.created_at)
    rmin, rmax, ravg = (
        db.query(func.min(sec), func.max(sec), func.avg(sec))
        .select_from(ErrorTask)
        .filter(
            ErrorTask.project_id == pid,
            ErrorTask.is_resolved.is_(True),
            ErrorTask.resolved_at.isnot(None),
        )
        .one()
    )

    def fmt_minutes(sec_val: float | None) -> str:
        if sec_val is None:
            return "—"
        return f"{float(sec_val) / 60.0:.1f} мин"

    start, end = default_range_days(7)
    m = aggregate_metrics(db, start, end, pid)

    lines = [
        f"📊 <b>Статистика проекта</b> «{proj.name}»",
        f"<code>{proj.id}</code>",
        "",
        "<b>Все время (задачи этого проекта)</b>",
        f"📌 Всего: {total} | ✅ решено: {resolved} | 🔄 в работе: {in_progress} | ⏳ ждут: {waiting}",
        f"⏱️ Время решения (все решённые): min {fmt_minutes(rmin)} | max {fmt_minutes(rmax)} | ср. {fmt_minutes(ravg)}",
        "",
        f"<b>За 7 дней</b> ({start.date()} — {end.date()})",
        f"Событий с ошибкой: {m['events_with_errors']}",
        f"Задач создано: {m['tasks_created']} | решено: {m['tasks_resolved']}",
    ]
    rts = m["resolution_time_seconds"]
    if rts["avg"] is not None:
        lines.append(
            f"⏱️ Решение (задачи за период): min {fmt_minutes(rts['min'])} | max {fmt_minutes(rts['max'])} | ср. {fmt_minutes(rts['avg'])}"
        )
    else:
        lines.append("⏱️ Решение (задачи за период): нет решённых задач в выбранные 7 дней")
    if m["top_domains"][:3]:
        doms = ", ".join(f"{d['domain']}: {d['count']}" for d in m["top_domains"][:3])
        lines.append(f"🌍 Чаще по доменам: {doms}")
    if m["top_who_took_task"][:3]:
        took = ", ".join(f"{x['label']}: {x['count']}" for x in m["top_who_took_task"][:3])
        lines.append(f"👷 Больше брали в работу: {took}")
    if m["top_who_resolved"][:3]:
        rs = ", ".join(f"{x['label']}: {x['count']}" for x in m["top_who_resolved"][:3])
        lines.append(f"✅ Больше закрыли: {rs}")
    return lines


@dp.callback_query(F.data.in_({"menu_stats", "menu_report", "menu_help"}))
async def menu_callback(callback_query: types.CallbackQuery):
    """Кнопки подсказок: статистика, отчёт, справка."""
    data = callback_query.data or ""
    chat = callback_query.message.chat if callback_query.message else None

    if data == "menu_help":
        await _safe_callback_answer(callback_query, "Открыта справка")
        if callback_query.message:
            await callback_query.message.answer(HELP_HTML, parse_mode="HTML", reply_markup=main_menu_keyboard())
        return

    if not chat:
        await _safe_callback_answer(callback_query, "Нет чата")
        return

    db = SessionLocal()
    try:
        proj = project_for_telegram_chat(db, chat.id)
        if not proj:
            await _safe_callback_answer(
                callback_query,
                "Сначала привяжите чат к проекту на коллекторе (/register)",
                show_alert=True,
            )
            return

        if data == "menu_stats":
            lines = _format_project_stats_lines(db, proj)
            await _safe_callback_answer(callback_query, "Сводка ниже")
            await callback_query.message.answer("\n".join(lines), parse_mode="HTML")
            return

        if data == "menu_report":
            await _safe_callback_answer(callback_query, "Формирую файл…")
            start, end = default_range_days(7)
            label = f"{proj.name} ({proj.id})"
            blob = build_excel_report(db, start, end, proj.id, project_label=label)
            cap = f"«{proj.name}» — {start.date()} — {end.date()}"
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in proj.name)[:40]
            fname = f"report_{safe_name}_{start.date()}_{end.date()}.xlsx"
            await callback_query.message.answer_document(
                BufferedInputFile(blob, filename=fname),
                caption=cap,
            )
    except Exception as e:
        logger.error("menu_callback: %s", e, exc_info=True)
        await _safe_callback_answer(callback_query, "Ошибка при выполнении", show_alert=True)
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
        "Нажми на кнопку под сообщением об ошибке, чтобы начать работу или отметить задачу как решённую.\n\n"
        "Команды в <b>чате проекта</b> (туда же, куда приходят алерты): /stats — сводка по этому проекту, /report — Excel за 7 дней.\n\n"
        "В личных сообщениях боту статистика недоступна — неизвестно, какой проект считать.\n\n"
        "Алерты уходят в Telegram-чат, указанный при регистрации на коллекторе (<code>/register</code>).\n\n"
        "<b>Кнопки ниже</b> — быстрый доступ (в чате проекта). Список команд также в меню Telegram (кнопка «Menu»).",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_HTML, parse_mode="HTML", reply_markup=main_menu_keyboard())

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

        chat = message.chat
        if chat and is_group_like_chat(chat.type):
            proj = project_for_telegram_chat(db, chat.id)
            if proj and task.project_id != proj.id:
                await message.answer(
                    "❌ Эта задача относится к <b>другому проекту</b>. "
                    "Команда /task в группе показывает только задачи своего проекта.",
                    parse_mode="HTML",
                )
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
            who = task.acknowledged_by_label or "—"
            response += f"▶️ <b>Взята в работу:</b> {task.acknowledged_at.strftime('%d.%m.%Y %H:%M:%S')} ({who})\n"
        if task.resolved_at:
            who_r = task.resolved_by_label or "—"
            response += f"✅ <b>Решена:</b> {task.resolved_at.strftime('%d.%m.%Y %H:%M:%S')} ({who_r})\n"
        if task.last_notification_sent_at:
            response += f"📨 <b>Последнее уведомление:</b> {task.last_notification_sent_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        await message.answer(response, parse_mode="HTML")
        
    finally:
        db.close()

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Сводка за 7 дней + счётчики задач только по проекту этого чата."""
    db = SessionLocal()
    try:
        chat = message.chat
        if not chat:
            await message.answer("Не удалось определить чат.")
            return

        proj = project_for_telegram_chat(db, chat.id)
        if not proj:
            await message.answer(
                "📊 Статистика считается <b>только в чате проекта</b>, куда приходят алерты.\n\n"
                "Убедитесь, что этот чат указан как <b>Telegram chat id</b> при регистрации проекта "
                "на коллекторе (страница <code>/register</code>). Затем вызовите /stats снова в этой группе.\n\n"
                "В личке бота проект не определить — откройте группу с уведомлениями.",
                parse_mode="HTML",
            )
            return

        lines = _format_project_stats_lines(db, proj)
        await message.answer("\n".join(lines), parse_mode="HTML")
    finally:
        db.close()


@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    """Excel-отчёт за последние 7 дней только по проекту этого чата."""
    chat = message.chat
    if not chat:
        await message.answer("Не удалось определить чат.")
        return

    db = SessionLocal()
    try:
        proj = project_for_telegram_chat(db, chat.id)
        if not proj:
            await message.answer(
                "📎 Отчёт доступен <b>только в чате проекта</b> с алертами "
                "(тот же chat id, что при <code>/register</code>).",
                parse_mode="HTML",
            )
            return

        start, end = default_range_days(7)
        label = f"{proj.name} ({proj.id})"
        blob = build_excel_report(db, start, end, proj.id, project_label=label)
        cap = f"«{proj.name}» — {start.date()} — {end.date()}"
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in proj.name)[:40]
        fname = f"report_{safe_name}_{start.date()}_{end.date()}.xlsx"
        await message.answer_document(
            BufferedInputFile(blob, filename=fname),
            caption=cap,
        )
    except Exception as e:
        logger.error("cmd_report: %s", e, exc_info=True)
        await message.answer("Не удалось сформировать отчёт. Проверьте логи коллектора.")
    finally:
        db.close()

async def main():
    """Запуск бота"""
    logger.info("🚀 Telegram bot started")
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning("Не удалось зарегистрировать команды меню Telegram: %s", e)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())