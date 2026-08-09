"""Тесты Expense Tracker: парсинг /add, автокатегоризация, слой БД."""
import asyncio
import csv
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from categories import FALLBACK_CATEGORY, categorize, parse_expense  # noqa: E402
from db import Database  # noqa: E402


# ------------------------------------------------------------- категории

def test_parse_expense_basic():
    parsed = parse_expense("500 кофе")
    assert parsed is not None
    amount, note, category = parsed
    assert amount == 500.0
    assert note == "кофе"
    assert category == "Продукты"


def test_parse_expense_comma_amount():
    parsed = parse_expense("99,50 булочка")
    assert parsed is not None
    assert parsed[0] == 99.50


def test_parse_expense_rejects_invalid():
    assert parse_expense("") is None
    assert parse_expense("abc") is None
    assert parse_expense("-10 кофе") is None
    assert parse_expense("0 кофе") is None
    assert parse_expense("999999999999 машина") is None  # превышение лимита
    assert parse_expense("500", max_amount=100) is None


def test_parse_expense_without_note():
    parsed = parse_expense("300")
    assert parsed is not None
    amount, note, category = parsed
    assert amount == 300.0
    assert note == ""
    assert category == FALLBACK_CATEGORY


def test_categorize_keywords_case_insensitive():
    assert categorize("поездка на МЕТРО") == "Транспорт"
    assert categorize("таблетки в аптеке") == "Здоровье"
    assert categorize("аренда квартиры") == "Жильё"


def test_categorize_fallback():
    assert categorize("случайная покупка") == FALLBACK_CATEGORY


# ------------------------------------------------------------------- БД

def test_db_roundtrip_and_aggregates(tmp_path):
    db_path = str(tmp_path / "expenses.db")

    async def run():
        db = Database(db_path)
        await db.init()
        user_id = 42
        await db.add_expense(user_id, 200.0, "Продукты", "обед", day=date(2026, 7, 30))
        await db.add_expense(user_id, 500.0, "Продукты", "кофе", day=date(2026, 8, 7))
        await db.add_expense(user_id, 300.0, "Транспорт", "метро", day=date(2026, 8, 6))

        assert await db.total_between(user_id, date(2026, 8, 1), date(2026, 8, 31)) == 800.0
        assert await db.total_between(user_id, date(2026, 7, 1), date(2026, 7, 31)) == 200.0

        by_cat = await db.by_category(user_id, date(2026, 8, 1), date(2026, 8, 31))
        assert by_cat == {"Продукты": 500.0, "Транспорт": 300.0}

        recent = await db.recent(user_id, limit=2)
        assert len(recent) == 2
        assert recent[0]["amount"] == 300.0  # последняя добавленная (id DESC) первая
        assert recent[1]["amount"] == 500.0

        # экспорт CSV
        csv_path = str(tmp_path / "export.csv")
        count = await db.export_csv(csv_path, user_id, date(2026, 8, 1), date(2026, 8, 31))
        assert count == 2
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        assert rows[0] == ["date", "category", "amount", "note"]
        assert len(rows) == 3  # шапка + 2 записи

    asyncio.run(run())


def test_db_empty_results(tmp_path):
    db_path = str(tmp_path / "empty.db")

    async def run():
        db = Database(db_path)
        await db.init()
        assert await db.total_between(1, date(2026, 1, 1), date(2026, 1, 31)) == 0.0
        assert await db.by_category(1, date(2026, 1, 1), date(2026, 1, 31)) == {}
        assert await db.recent(1) == []

    asyncio.run(run())


def test_undo_flow(tmp_path) -> None:
    """/undo: удаляется последняя запись, предыдущая остаётся."""
    db_path = str(tmp_path / "undo.db")

    async def run():
        db = Database(db_path)
        await db.init()
        assert await db.last_expense(1) is None
        await db.add_expense(1, 100, "Продукты", "кофе")
        await db.add_expense(1, 200, "Транспорт", "такси")
        last = await db.last_expense(1)
        assert last["amount"] == 200.0
        assert await db.delete_expense(1, last["id"]) is True
        assert (await db.last_expense(1))["amount"] == 100.0  # осталась первая
        assert await db.delete_expense(1, last["id"]) is False  # повторное — False

    asyncio.run(run())
