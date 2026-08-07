"""Конфигурация Expense Tracker Bot через переменные окружения."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("EXPENSE_BOT_TOKEN", "")
DB_PATH = os.getenv("EXPENSE_DB_PATH", os.path.join(BASE_DIR, "expenses.db"))

# Минимальный интервал между сообщениями пользователя (секунды)
THROTTLE_MIN_INTERVAL = float(os.getenv("THROTTLE_MIN_INTERVAL", "0.7"))

# Лимит суммы расхода (защита от опечаток вроде /add 500000000)
MAX_AMOUNT = float(os.getenv("MAX_AMOUNT", "1000000"))
