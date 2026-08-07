FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# docker run -e EXPENSE_BOT_TOKEN=... -v expenses_vol:/app ...
CMD ["python", "bot.py"]
