"""
Точка входа: Telegram-бот на aiogram 3 + заглушка для Render + webhook DonatePay
"""
import asyncio
import logging
from threading import Thread
from flask import Flask, request
import os
import hashlib
import hmac
import re
import json
import io as io_module
from PIL import Image

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    URLInputFile,
)

from config import TELEGRAM_BOT_TOKEN
from ai_service import analyze_photo, generate_image
from image_utils import download_and_resize, image_to_bytes, draw_hints
from stats import add_analysis, get_stats
from course import (
    get_status,
    add_photo,
    check_day,
    has_access,
    get_day_photos,
    get_next_day,
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

flask_app = Flask(__name__)

# ===== ПЕРСИСТЕНТНЫЕ ДАННЫЕ =====
user_mode = {}
free_generations = {}
paid_generations = {}
last_photo = {}
gen_wish = {}
gen_format = {}

GEN_FILE = "generations.json"
MODE_FILE = "user_mode.json"

def _load_gen():
    global free_generations, paid_generations
    if os.path.exists(GEN_FILE):
        with open(GEN_FILE, "r") as f:
            data = json.load(f)
            free_generations = {int(k): v for k, v in data.get("free", {}).items()}
            paid_generations = {int(k): v for k, v in data.get("paid", {}).items()}

def _save_gen():
    with open(GEN_FILE, "w") as f:
        json.dump({
            "free": {str(k): v for k, v in free_generations.items()},
            "paid": {str(k): v for k, v in paid_generations.items()},
        }, f)

def _load_mode():
    global user_mode
    if os.path.exists(MODE_FILE):
        with open(MODE_FILE, "r") as f:
            data = json.load(f)
            user_mode = {int(k): v for k, v in data.items()}

def _save_mode():
    with open(MODE_FILE, "w") as f:
        json.dump({str(k): v for k, v in user_mode.items()}, f)

_load_gen()
_load_mode()

# ===== FLASK =====
@flask_app.route('/')
def home():
    return "Bot is running"

@flask_app.route('/donate-webhook', methods=['POST'])
def donate_webhook():
    API_KEY = "pytBdeWXxqGPKL0PW5jLL2QdKCLfDjSiL614W0bZbMehtBMSA7VhE31ylqRE"

    body = request.get_data().decode('utf-8')
    signature = request.headers.get('X-DonatePay-Signature', '')
    expected = hashlib.sha256((body + API_KEY).encode()).hexdigest()

    if signature != expected:
        return 'Invalid signature', 403

    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        comment = data.get('comment', '')
        nickname = data.get('nickname', '')

        match = re.search(r'@(\w+)', comment)
        if not match:
            telegram_username = nickname
        else:
            telegram_username = match.group(1)

        if amount >= 490 and "курс" in comment.lower():
            from course import activate_by_username
            activate_by_username(telegram_username)

        if amount >= 99 and amount < 249 and "генерац" in comment.lower():
            paid_generations[telegram_username] = paid_generations.get(telegram_username, 0) + 5
            _save_gen()
        elif amount >= 249 and "генерац" in comment.lower():
            paid_generations[telegram_username] = paid_generations.get(telegram_username, 0) + 20
            _save_gen()

        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== КНОПКИ И ФОРМАТЫ =====
DONATE_LOGIN = "1515230"

SIZE_MAP = {
    "1:1": "1024x1024",
    "3:4": "768x1024",
    "4:3": "1024x768",
    "4:5": "896x1080",
    "16:9": "1280x720",
    "9:16": "720x1280",
}

FORMATS = [
    ("original", "📐 Исходный формат"),
    ("1_1", "📱 1:1 (квадрат)"),
    ("3_4", "📱 3:4 (вертикаль)"),
    ("4_3", "🖼️ 4:3 (горизонт)"),
    ("4_5", "📱 4:5 (вертикаль, Instagram)"),
    ("16_9", "🖼️ 16:9 (панорама)"),
    ("9_16", "📱 9:16 (сториз)"),
]

def format_keyboard(gen_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"gen_{fmt}_{gen_type}")]
        for fmt, name in FORMATS
    ])

def get_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []

    free_left = 5 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)

    if user_id == 456504792:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (автор)", callback_data="gen_free")])
    elif free_left > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото (бесплатно: {free_left})", callback_data="gen_free")])
    elif paid_left > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото (осталось {paid_left})", callback_data="gen_paid")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 5 улучшений — 99 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=99&comment=генерации")])
        buttons.append([InlineKeyboardButton(text="💛 20 улучшений — 249 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=249&comment=генерации")])

    if has_access(user_id) and user_mode.get(user_id) == "course":
        buttons.append([InlineKeyboardButton(text="📸 Продолжить курс", callback_data="mode_course")])
        buttons.append([InlineKeyboardButton(text="🔍 Просто анализ", callback_data="mode_free")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 Поддержать на 100 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=100")])
        buttons.append([InlineKeyboardButton(text="💛 Поддержать (любая сумма)", url=f"https://donatepay.ru/don/{DONATE_LOGIN}")])
        buttons.append([InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")])

    buttons.append([InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")])
    buttons.append([InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

AUTHOR_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
    ]
)

async def send_photos(chat_id: int, day: int):
    photos = get_day_photos(day)
    if not photos:
        return
    try:
        if len(photos) == 1:
            await bot.send_photo(chat_id, URLInputFile(photos[0]))
        elif len(photos) >= 2:
            media = [InputMediaPhoto(media=URLInputFile(photos[0]))]
            for url in photos[1:]:
                media.append(InputMediaPhoto(media=URLInputFile(url)))
            await bot.send_media_group(chat_id, media)
    except Exception as e:
        logging.error(f"Ошибка отправки фото: {e}")

# ===== ОСНОВНЫЕ КОМАНДЫ =====
@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "👋 Привет! Я — бот-наставник по мобильной фотографии.\n\n"
        "Пришли мне фото, и я найду композиционные ошибки: "
        "заваленный горизонт, мусор в кадре, неудачную позу и другое. "
        "Ты получишь фото с подсказками прямо на нём и короткий разбор от профи. 📸\n\n"
        "✨ <b>Новинка:</b> теперь можно сгенерировать исправленную версию фото с помощью ИИ!",
        reply_markup=AUTHOR_KEYBOARD,
        parse_mode="HTML",
    )

@dp.message(Command("author"))
async def handle_author(message: Message):
    await message.answer(
        "📸 <b>Автор бота — Евгений Севостьянов</b>\n"
        "Фотограф, преподаватель мобильной фотографии.\n\n"
        "📷 Instagram: <a href='https://instagram.com/sevosphoto'>@sevosphoto</a>\n"
        "💬 Telegram: <a href='https://t.me/sevosphoto'>@sevosphoto</a>\n"
        "🌐 VK: <a href='https://vk.com/cevoc'>@cevoc</a>\n\n"
        "По вопросам сотрудничества и обучения — пишите в личные сообщения!",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

@dp.message(Command("stats"))
async def handle_stats(message: Message):
    text = get_stats(message.from_user.id)
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("course"))
async def handle_course(message: Message):
    if has_access(message.from_user.id):
        status = get_status(message.from_user.id)
        if status is not None:
            if "День 0" in status or "Подготовка" in status:
                await message.answer(
                    status,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")],
                        ]
                    ),
                )
                await send_photos(message.chat.id, 0)
            else:
                await message.answer(status, parse_mode="HTML")
                from course
