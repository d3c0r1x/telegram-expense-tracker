# Telegram Expense Tracker 🧾

Личный трекер расходов в Telegram: запись трат одной строкой, автоматическая
категоризация, отчёты по периодам и категориям, экспорт в CSV (открывается в Excel).

## Возможности

| Команда | Описание |
|---|---|
| `/add 500 кофе` | Записать расход: сумма + примечание, категория определится сама |
| `/today` `/week` `/month` | Итого за сегодня / 7 дней / месяц |
| `/report` | Разбивка по категориям с долями |
| `/recent` | Последние 10 записей |
| `/export` | CSV-файл за месяц (utf-8-sig — Excel-совместимый) |

## Продвинутый уровень (v2)

- **Автокатегоризация** по ключевым словам — чистая функция `parse_expense`
  (парсинг суммы с запятой, лимит суммы, фолбэк-категория «Разное»), покрыта
  unit-тестами без Telegram и БД;
- **Агрегаты в SQL** — итоги и разбивка по категориям считаются запросами по
  диапазону дат (`GROUP BY`, `BETWEEN`), без загрузки всех строк в память;
- **Индекс** `(user_id, created_at)` под все отчёты;
- **CSV с BOM** (`utf-8-sig`) — кириллица корректно открывается в Excel;
- **Middlewares** — троттлинг (анти-спам) и логирование;
- **Лимит суммы** — защита от опечаток вроде `/add 500000000`.

## Структура

```
telegram-expense-tracker/
├── bot.py            # aiogram v3: команды, форматирование сумм, экспорт
├── config.py         # переменные окружения (токен, лимит суммы)
├── categories.py     # ЧИСТЫЕ функции: categorize(), parse_expense()
├── db.py             # aiosqlite: расходы, агрегаты, CSV-экспорт
├── middlewares.py    # троттлинг + логирование
├── tests/            # unit-тесты парсинга, категорий и БД
├── requirements.txt
├── pyproject.toml
├── Dockerfile        # docker run -e EXPENSE_BOT_TOKEN=...
├── .github/workflows/ci.yml  # CI: compileall + pytest на каждый push
└── run_bot8.cmd      # запуск в Windows (читает TG_TOKEN из корневого .env)
```

## Запуск

```bash
pip install -r requirements.txt
set EXPENSE_BOT_TOKEN=123456:ABC...
python bot.py
```

Или в Windows — двойной клик по `run_bot8.cmd` (токен берётся из `..\.env`).

## Пример

```
Вы:   /add 500 кофе
Бот:  ✅ Записано: 500,00 ₽ — кофе
      🏷 Категория: Продукты (№1)

Вы:   /report
Бот:  📊 Расходы за месяц: 5 430,00 ₽
      Продукты — 2 300,00 ₽ (42%)
      Транспорт — 1 200,00 ₽ (22%)
      ...
```

## Тесты

```bash
python -m pytest tests/ -q
```

## Docker

```bash
docker build -t telegram-expense-tracker .
docker run -e EXPENSE_BOT_TOKEN=... telegram-expense-tracker
```
