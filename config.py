"""
Загрузка переменных окружения (токены API)
"""
import os

# На Render переменные окружения передаются через Environment Variables,
# локально — через файл .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN. Добавь в .env или Environment Variables")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY. Добавь в .env или Environment Variables")
