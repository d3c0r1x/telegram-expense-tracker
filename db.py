"""SQLite-БД расходов (aiosqlite).

Схема:
  expenses(id INTEGER PK, user_id, amount REAL, category TEXT, note TEXT,
           created_at TEXT)  — created_at = дата 'YYYY-MM-DD' (UTC)

Агрегаты считаются SQL-запросами по диапазону дат (today/week/month) —
продвинутый приём: никакой загрузки всех строк в память.
"""
from __future__ import annotations

import csv
from datetime import date

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    amount     REAL NOT NULL,
                    category   TEXT NOT NULL,
                    note       TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            # Индекс: агрегаты идут по (user_id, created_at)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_user_date "
                "ON expenses (user_id, created_at)"
            )
            await db.commit()

    async def add_expense(
        self, user_id: int, amount: float, category: str, note: str, day: date | None = None
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO expenses (user_id, amount, category, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, note, (day or date.today()).isoformat()),
            )
            await db.commit()
            return cur.lastrowid

    async def total_between(self, user_id: int, start: date, end: date) -> float:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                "WHERE user_id = ? AND created_at BETWEEN ? AND ?",
                (user_id, start.isoformat(), end.isoformat()),
            )
            row = await cur.fetchone()
        return float(row[0])

    async def by_category(self, user_id: int, start: date, end: date) -> dict[str, float]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT category, SUM(amount) AS total FROM expenses "
                "WHERE user_id = ? AND created_at BETWEEN ? AND ? "
                "GROUP BY category ORDER BY total DESC",
                (user_id, start.isoformat(), end.isoformat()),
            )
            rows = await cur.fetchall()
        return {str(r[0]): float(r[1]) for r in rows}

    async def recent(self, user_id: int, limit: int = 10) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def export_csv(self, path: str, user_id: int, start: date, end: date) -> int:
        """Выгружает расходы за период в CSV (utf-8-sig — открывается в Excel)."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT created_at, category, amount, note FROM expenses "
                "WHERE user_id = ? AND created_at BETWEEN ? AND ? "
                "ORDER BY created_at",
                (user_id, start.isoformat(), end.isoformat()),
            )
            rows = await cur.fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow(["date", "category", "amount", "note"])
            for r in rows:
                writer.writerow([r["created_at"], r["category"], r["amount"], r["note"]])
        return len(rows)
