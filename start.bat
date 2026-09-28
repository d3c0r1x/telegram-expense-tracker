@echo off
rem Launch script for Telegram Expense Tracker (Project 8).
rem Reads TG_TOKEN from the root .env, sets EXPENSE_BOT_TOKEN, runs the bot.
cd /d "%~dp0"

for /f "usebackq tokens=1,* delims==" %%a in ("..\.env") do (
    if "%%a"=="TG_TOKEN" set "EXPENSE_BOT_TOKEN=%%b"
)
if not defined EXPENSE_BOT_TOKEN (
    echo [ERROR] TG_TOKEN not found in ..\.env
    pause
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"

..\.venv\Scripts\python.exe -u bot.py
