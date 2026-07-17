"""
Загрузка переменных окружения (токены API) из файла .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN в .env файле")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY в .env файле")