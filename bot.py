"""Telegram Expense Tracker (aiogram v3 + aiosqlite).

Стек: aiogram v3 (Telegram Bot API) + aiosqlite (хранение расходов) —
без внешних платных сервисов; вся «магия» на чистом Python.

Команды:
  /add 500 кофе        — записать расход (сумма + примечание, автокатегория)
  /today /week /month  — итого за период
  /report              — разбивка по категориям (кто съедает бюджет)
  /recent              — последние 10 записей
  /export              — CSV-файл расходов за месяц (открывается в Excel)

Продвинутый уровень:
  - автокатегоризация по ключевым словам (чистая функция, unit-тесты);
  - агрегаты считаются SQL-запросами по диапазону дат — без загрузки
    всех строк в память;
  - экспорт CSV в кодировке utf-8-sig (совместим с Excel);
  - middlewares: троттлинг и логирование.

Запуск:  python bot.py   (задайте EXPENSE_BOT_TOKEN, или run_bot8.cmd).
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
import os
from datetime import date, timedelta

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message

import config
from categories import parse_expense
from db import Database
from middlewares import LoggingMiddleware, ThrottlingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.BASE_DIR, "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

router = Router()
db = Database(config.DB_PATH)

START_TEXT = (
    "🧾 <b>Telegram Expense Tracker</b>\n\n"
    "/add 500 кофе — записать расход\n"
    "/today — расходы за сегодня\n"
    "/week — за 7 дней\n"
    "/month — за месяц\n"
    "/report — по категориям\n"
    "/recent — последние записи\n"
    "/export — выгрузить месяц в CSV\n\n"
    "Формат расхода: сумма + примечание (категория определится сама)."
)


def _money(value: float) -> str:
    """1000.5 → '1 000,50 ₽' — человекочитаемый вывод суммы."""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _period_dates(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "today":
        return today, today
    if period == "week":
        return today - timedelta(days=6), today
    return today.replace(day=1), today  # month


# ---------------------------------------------------------------- команды

@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    parsed = parse_expense(args[1] if len(args) > 1 else "", max_amount=config.MAX_AMOUNT)
    if parsed is None:
        await message.answer(
            "⚠️ Не понял формат. Пример: <code>/add 500 кофе</code>\n"
            f"Сумма — число от 0 до {config.MAX_AMOUNT:,.0f}."
        )
        return
    amount, note, category = parsed
    row_id = await db.add_expense(message.from_user.id, amount, category, note)
    await message.answer(
        f"✅ Записано: <b>{_money(amount)}</b> — {_html.escape(note or category)}\n"
        f"🏷 Категория: <b>{_html.escape(category)}</b> (№{row_id})"
    )


@router.message(Command("today"))
@router.message(Command("week"))
@router.message(Command("month"))
async def cmd_period(message: Message) -> None:
    period = message.text.lstrip("/").split()[0]
    start, end = _period_dates(period)
    total = await db.total_between(message.from_user.id, start, end)
    labels = {"today": "сегодня", "week": "за 7 дней", "month": "в этом месяце"}
    await message.answer(
        f"💸 Расходы <b>{labels[period]}</b>: <b>{_money(total)}</b>"
    )


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    start, end = _period_dates("month")
    by_cat = await db.by_category(message.from_user.id, start, end)
    if not by_cat:
        await message.answer("В этом месяце расходов пока нет. Добавьте первый: /add 500 кофе")
        return
    total = sum(by_cat.values())
    lines = [f"📊 <b>Расходы за месяц: {_money(total)}</b>\n"]
    lines += [
        f"{_html.escape(cat)} — <b>{_money(v)}</b> "
        f"({v / total * 100:.0f}%)"
        for cat, v in by_cat.items()
    ]
    await message.answer("\n".join(lines))


@router.message(Command("recent"))
async def cmd_recent(message: Message) -> None:
    rows = await db.recent(message.from_user.id, limit=10)
    if not rows:
        await message.answer("Записей пока нет. Добавьте первую: /add 500 кофе")
        return
    lines = ["🕘 <b>Последние записи</b>"]
    lines += [
        f"{r['created_at']} · <b>{_money(r['amount'])}</b> "
        f"({_html.escape(r['category'])}) {_html.escape(r['note'])}"
        for r in rows
    ]
    await message.answer("\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    start, end = _period_dates("month")
    path = os.path.join(config.BASE_DIR, f"export_{message.from_user.id}.csv")
    count = await db.export_csv(path, message.from_user.id, start, end)
    if count == 0:
        await message.answer("За этот месяц записей нет — экспортировать нечего.")
        return
    await message.answer_document(
        FSInputFile(path, filename=f"expenses_{start.isoformat()}_{end.isoformat()}.csv"),
        caption=f"📄 Расходы за месяц: {count} записей, "
                f"итого {_money(await db.total_between(message.from_user.id, start, end))}",
    )


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан EXPENSE_BOT_TOKEN. Скопируйте .env.example и задайте токен.")
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    dp.message.middleware(ThrottlingMiddleware(min_interval=config.THROTTLE_MIN_INTERVAL))
    dp.update.middleware(LoggingMiddleware())
    await db.init()
    logger.info("Expense Tracker запущен.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
