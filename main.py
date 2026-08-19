"""
Точка входа: Telegram-бот на aiogram 3 + заглушка для Render
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
import base64
import io as io_module
from PIL import Image, ImageChops
from datetime import datetime

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
from ai_service import analyze_photo, generate_image, create_payment_link, _load_pending_payments
from image_utils import download_and_resize, image_to_bytes, draw_hints
from stats import add_analysis, get_stats, add_history as stats_add_history, _load_stats as load_stats_data
from course import get_status, add_photo, check_day, has_access, get_day_photos, _load_users, activate_free_trial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

MAIN_LOOP = None
flask_app = Flask(__name__)

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

USER_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Анализ фото"), KeyboardButton(text="✂️ Редактор")],
        [KeyboardButton(text="📷 Flat Lay"), KeyboardButton(text="🎨 Стилизация")],
        [KeyboardButton(text="🎯 Авторский разбор"), KeyboardButton(text="🎓 Мини-курс")],
        [KeyboardButton(text="🏠 Главное меню")],
    ],
    resize_keyboard=True
)

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Админка"), KeyboardButton(text="🎫 Промо")],
        [KeyboardButton(text="📸 Заказы"), KeyboardButton(text="🧪 Тест")],
        [KeyboardButton(text="🔄 Сброс курса"), KeyboardButton(text="📋 Старт")],
    ],
    resize_keyboard=True
)

# ===== ХРАНИЛИЩА ДАННЫХ =====
last_analysis = {}
user_mode = {}
free_generations = {}
paid_generations = {}
GEN_FILE = "generations.json"
last_photo = {}
original_photo = {}
gen_wish = {}
gen_format = {}
gen_retry_count = {}
gen_used_count = {}
flat_lay_active = {}
flat_lay_style = {}  # НОВОЕ: хранит выбранный стиль Flat Lay
change_format_warnings = {}
test_mode = False

HISTORY_FILE = "history.json"
PROMO_FILE = "promocodes.json"
FEEDBACK_FILE = "feedback.json"
AUTHOR_ORDERS_FILE = "author_orders.json"
AUTHOR_PHOTOS_DIR = "author_photos"

def _load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_history(history: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def _load_promo() -> dict:
    if not os.path.exists(PROMO_FILE):
        return {}
    with open(PROMO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_promo(promo: dict):
    with open(PROMO_FILE, "w", encoding="utf-8") as f:
        json.dump(promo, f, ensure_ascii=False, indent=2)

def _save_feedback(entry: dict):
    feedback = []
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            feedback = json.load(f)
    feedback.append(entry)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)

def _load_author_orders() -> list:
    if not os.path.exists(AUTHOR_ORDERS_FILE):
        return []
    with open(AUTHOR_ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_author_orders(orders: list):
    with open(AUTHOR_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def _save_author_photo(order_time: str, index: int, image_bytes: bytes) -> str:
    os.makedirs(AUTHOR_PHOTOS_DIR, exist_ok=True)
    filename = f"{order_time.replace(':','-').replace('.','-')}_{index}.jpg"
    filepath = os.path.join(AUTHOR_PHOTOS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filename

def _add_history(user_id: int, action: str, details: str = ""):
    stats_add_history(user_id, action, details)

# ===== ГЕНЕРАЦИИ =====
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
    ("4_5", "📱 4:5 (Instagram)"),
    ("16_9", "🖼️ 16:9 (панорама)"),
    ("9_16", "📱 9:16 (сториз)"),
]

def get_size_for_format(fmt: str, image_bytes: bytes = None) -> str:
    if fmt == "original" and image_bytes:
        try:
            img = Image.open(io_module.BytesIO(image_bytes))
            w, h = img.size
            w = max(512, (w // 64) * 64)
            h = max(512, (h // 64) * 64)
            return f"{w}x{h}"
        except Exception:
            pass
    key = fmt.replace("_", ":")
    return SIZE_MAP.get(key, "1024x1024")

def format_keyboard(gen_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"gen_{fmt}_{gen_type}")]
        for fmt, name in FORMATS
    ])

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

_load_gen()

# ===== FLAT LAY ДАННЫЕ =====
FLAT_LAY_STYLES = {
    "cozy": "☕ Уютный",
    "minimal": "⬜ Минимализм",
    "nature": "🌿 Природный",
    "dark": "🖤 Тёмный",
    "pastel": "🌸 Нежный",
}

FLAT_LAY_PROMPTS = {
    "cozy": (
        "Создай стильный УЮТНЫЙ Flat Lay как из Pinterest. "
        "Полностью замени фон на чистый тёплый деревянный стол. "
        "РАССТАВЬ предметы красиво и гармонично — ПОЛНОСТЬЮ измени их расположение, порядок и углы. "
        "Улучши внешний вид предметов: убери грязь, пятна, потёки. "
        "Добавь БОГАТЫЙ уместный декор: "
        "если это кофе — кофейные зёрна, корицу, печенье, салфетку; "
        "если чай — чайные листья, мёд, лимон, печенье; "
        "если еда — приборы, специи, зелень, салфетку; "
        "если косметика — ватные диски, цветы, ленту. "
        "ЕСЛИ есть чашка — НАПОЛНИ её чаем или кофе. "
        "Мягкий тёплый свет, уютная атмосфера. "
        "Сохрани все предметы с фото."
    ),
    "minimal": (
        "Создай МИНИМАЛИСТИЧНЫЙ Flat Lay как из Pinterest. "
        "Полностью замени фон на чистый белый. "
        "РАССТАВЬ предметы идеально — ПОЛНОСТЬЮ измени их расположение, создай геометричную композицию. "
        "Улучши вид предметов: убери грязь, пятна. "
        "Добавь МИНИМУМ уместного декора. "
        "Много пустого пространства. "
        "ЕСЛИ есть чашка — НАПОЛНИ её напитком. "
        "Мягкий рассеянный свет. "
        "Сохрани все предметы."
    ),
    "nature": (
        "Создай ПРИРОДНЫЙ Flat Lay как из Pinterest. "
        "Полностью замени фон на чистый светлый мрамор или светлое дерево. "
        "РАССТАВЬ предметы гармонично — ПОЛНОСТЬЮ измени расположение. "
        "Улучши вид предметов: убери грязь, пятна. "
        "Добавь ЖИВЫЕ зелёные листья, эвкалипт, цветы. "
        "НЕ добавляй сухую траву. "
        "ЕСЛИ есть чашка — НАПОЛНИ её напитком. "
        "Мягкий дневной свет. "
        "Сохрани все предметы."
    ),
    "dark": (
        "Создай ЭЛЕГАНТНЫЙ ТЁМНЫЙ Flat Lay как из Pinterest. "
        "Полностью замени фон на чистый тёмный матовый или тёмное дерево. "
        "РАССТАВЬ предметы стильно — ПОЛНОСТЬЮ измени расположение. "
        "Улучши вид предметов: убери грязь, пятна. "
        "Добавь уместный тёмный декор. "
        "ЕСЛИ есть чашка — НАПОЛНИ её напитком. "
        "Драматичный свет, глубокие тени. "
        "Сохрани все предметы."
    ),
    "pastel": (
        "Создай НЕЖНЫЙ ПАСТЕЛЬНЫЙ Flat Lay как из Pinterest. "
        "Полностью замени фон на чистый пастельный. "
        "РАССТАВЬ предметы красиво — ПОЛНОСТЬЮ измени расположение. "
        "Улучши вид предметов: убери грязь, пятна. "
        "Добавь живые цветы, мягкий свет. "
        "ЕСЛИ есть чашка — НАПОЛНИ её напитком. "
        "Сохрани все предметы."
    ),
}

# ===== FLASK =====
@flask_app.route('/')
def home():
    return "Bot is running"

def _send_telegram_message(uid, text):
    global MAIN_LOOP
    if MAIN_LOOP is None:
        logger.error("MAIN_LOOP не инициализирован")
        return
    try:
        asyncio.run_coroutine_threadsafe(bot.send_message(uid, text), MAIN_LOOP)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение: {e}")

@flask_app.route('/webhook/tochka', methods=['POST'])
def tochka_webhook():
    try:
        raw_body = request.get_data(as_text=True)
        logger.info(f"🔔 Вебхук Точки (первые 200 символов): {raw_body[:200]}")
        try:
            data = json.loads(raw_body)
            logger.info(f"🔔 JSON: {json.dumps(data, ensure_ascii=False)[:300]}")
            return "OK", 200
        except json.JSONDecodeError:
            pass
        parts = raw_body.split('.')
        if len(parts) == 3:
            payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
            decoded = base64.b64decode(payload_b64).decode('utf-8')
            webhook_data = json.loads(decoded)
            logger.info(f"🔔 Вебхук расшифрован: {json.dumps(webhook_data, ensure_ascii=False)[:500]}")
            amount = float(webhook_data.get("amount", 0))
            purpose = webhook_data.get("purpose", "")
            payment_link_id = webhook_data.get("paymentLinkId", "")
            logger.info(f"💰 Платёж: {amount} ₽, назначение: {purpose}")
            if payment_link_id:
                pending = _load_pending_payments()
                if payment_link_id in pending:
                    info = pending[payment_link_id]
                    uid = info["user_id"]
                    purp = info["purpose"]
                    payer = webhook_data.get("payerName", "Неизвестный")
                    notify_text = f"💰 <b>Новый платёж!</b>\nСумма: {amount} ₽\nНазначение: {purp}\nПлательщик: {payer}\nID пользователя: <code>{uid}</code>"
                    _send_telegram_message(-1004468971541, notify_text)
                    if "Пакет 10 генераций" in purp:
                        paid_generations[uid] = paid_generations.get(uid, 0) + 10
                        _save_gen()
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "✅ Оплата получена! 10 генераций начислены."), MAIN_LOOP)
                    elif "Пакет 30 генераций" in purp:
                        paid_generations[uid] = paid_generations.get(uid, 0) + 30
                        _save_gen()
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "✅ Оплата получена! 30 генераций начислены."), MAIN_LOOP)
                    elif "Авторский разбор" in purp:
                        orders = _load_author_orders()
                        orders.append({
                            "user_id": uid,
                            "username": f"id{uid}",
                            "photos": [],
                            "status": "paid",
                            "time": datetime.now().isoformat()
                        })
                        _save_author_orders(orders)
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "✅ Оплата получена! Присылай до 5 фото по одному. Нажми «Готово» когда закончишь."), MAIN_LOOP)
                        _send_telegram_message(-1004468971541, f"🔔 Новый заказ на авторский разбор!\nПользователь: {uid}")
                    elif "мини-курс" in purp or "курс" in purp:
                        from course import activate_by_username
                        activate_by_username(str(uid))
                        user_mode[uid] = "course"
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "✅ Оплата получена! Мини-курс активирован. Напиши /course"), MAIN_LOOP)
                    else:
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "💛 Спасибо за поддержку проекта!"), MAIN_LOOP)
                    del pending[payment_link_id]
                    with open("pending_payments.json", "w") as f:
                        json.dump(pending, f, ensure_ascii=False, indent=2)
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return "OK", 200

def _setup_webhook():
    try:
        import requests as req
        from config import TOCHKA_API_TOKEN
        client_id = "5e3f88c12690b3086faf7fa0daf46efa"
        url = f"https://enter.tochka.com/uapi/webhook/v1.0/{client_id}"
        headers = {
            "Authorization": f"Bearer {TOCHKA_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "webhooksList": ["acquiringInternetPayment"],
            "url": "https://photo-bot-6koz.onrender.com/webhook/tochka"
        }
        response = req.put(url, json=payload, headers=headers, timeout=15)
        logger.info(f"🔧 Создание вебхука: статус {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка создания вебхука: {e}")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    _setup_webhook()
    flask_app.run(host='0.0.0.0', port=port)

# ===== КЛАВИАТУРЫ =====
def donate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 100 ₽", callback_data="donate_100"),
         InlineKeyboardButton(text="💛 300 ₽", callback_data="donate_300"),
         InlineKeyboardButton(text="💛 500 ₽", callback_data="donate_500")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])

def get_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    free_left = 5 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)
    total_left = free_left + paid_left
    
    if user_id == 456504792 and not test_mode:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (автор)", callback_data="gen_free")])
    elif free_left > 0:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (5 бесплатно)", callback_data="gen_free")])
    elif paid_left > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото (осталось {paid_left})", callback_data="gen_paid")])
    else:
        buttons.append([InlineKeyboardButton(text="⚡ 10 улучшений — 99 ₽", callback_data="buy_10_gen")])
        buttons.append([InlineKeyboardButton(text="⚡ 30 улучшений — 249 ₽", callback_data="buy_30_gen")])
    if has_access(user_id) and user_mode.get(user_id) == "course" and not test_mode:
        buttons.append([InlineKeyboardButton(text="📸 Продолжить курс", callback_data="mode_course")])
        buttons.append([InlineKeyboardButton(text="🔍 Просто анализ", callback_data="mode_free")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 Поддержать проект", callback_data="donate_menu")])
        buttons.append([InlineKeyboardButton(text="🎓 Мини-курс по композиции (490 ₽)", callback_data="course_status")])
    buttons.append([InlineKeyboardButton(text=f"💎 Мои генерации: {total_left}", callback_data="my_balance")])
    buttons.append([InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")])
    buttons.append([InlineKeyboardButton(text="📐 Сменить формат этого фото", callback_data="change_format_same")])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
async def send_photos(chat_id: int, day: int):
    photos = get_day_photos(day)
    if not photos:
        return
    try:
        await bot.send_photo(chat_id, URLInputFile(photos[0]))
    except Exception as e:
        logger.error(f"Ошибка отправки первого фото: {e}")
    for url in photos[1:]:
        try:
            await bot.send_photo(chat_id, URLInputFile(url))
        except Exception:
            pass

async def do_generation(user_id: int, chat_id: int, gen_type: str, check_diff: bool = True, use_original: bool = False, mode: str = "normal"):
    """Выполняет генерацию изображения."""
    if user_id not in last_photo:
        await bot.send_message(chat_id, "Сначала пришли фото для анализа!")
        return
    
    fmt = gen_format.get(user_id, "1_1")
    wish = gen_wish.get(user_id, "")
    is_flat_lay = flat_lay_active.get(user_id, False)
    
    # Определяем, какое фото использовать
    if is_flat_lay:
        # Для Flat Lay: перегенерация берёт исходное, доработка — текущее
        if mode == "retry" and user_id in original_photo:
            image_bytes = original_photo[user_id]
        else:
            image_bytes = last_photo[user_id]
    elif use_original and user_id in original_photo:
        image_bytes = original_photo[user_id]
    else:
        image_bytes = last_photo[user_id]
    
    if wish and wish.lower() != "ок":
        await bot.send_message(chat_id, "🎨 Генерирую изображение по твоему пожеланию...")
    elif mode == "retry":
        await bot.send_message(chat_id, "🔄 Генерирую другой вариант...")
    elif mode == "boost":
        await bot.send_message(chat_id, "⚡ Усиливаю обработку...")
    else:
        await bot.send_message(chat_id, "🎨 Генерирую изображение...")
    
    try:
        img_size = get_size_for_format(fmt, image_bytes)
        analysis = last_analysis.get(user_id, {})
        error_type = analysis.get("error_type", "")
        what_is_wrong = analysis.get("what_is_wrong", "")
        
        # ===== ФОРМИРУЕМ ПРОМПТ =====
        if is_flat_lay:
            # Для Flat Lay — используем сохранённый стиль
            saved_style = flat_lay_style.get(user_id, "")
            if saved_style and saved_style in FLAT_LAY_PROMPTS:
                prompt = f"{FLAT_LAY_PROMPTS[saved_style]} Размер: {img_size}. "
            elif wish and wish.lower() != "ок":
                prompt = f"{wish} Размер: {img_size}. "
            else:
                prompt = f"Создай стильный Flat Lay. Размер: {img_size}. "
        else:
            # Обычный промпт для портретов/фото
            prompt = (
                f"Улучши это фото как опытный ретушёр. Сделай кадр гармоничным и естественным. "
                f"Дорисуй обрезанные края — особенно конечности. "
                f"Если ноги выглядят обрезанными краем кадра — дорисуй голени и стопы. "
                f"Если ноги спрятаны за объектом — не трогай этот объект. "
                f"Исправь неестественную позу. "
                f"Если объект прижат к краю или ему тесно — перестрой композицию: смести объект к трети, оставив воздух. "
                f"Убери только явно случайные объекты на фоне. "
                f"Если есть фрейминг — сделай его аккуратнее. "
                f"Улучши свет и цвета. "
                f"НЕ меняй черты лица — сохрани их в точности. "
                f"НЕ добавляй новые объекты, людей, животных, которых не было на исходном фото. Только улучшай существующее. "
                f"ВАЖНО: сохрани стиль одежды и обуви человека с исходного фото. Если нужно дорисовать ноги или одежду — дорисовывай в том же стиле, что и оригинал. НЕ меняй стиль одежды на другой. "
                f"ВАЖНО: сохрани все украшения и аксессуары с исходного фото. Если на фото нет колец — НЕ дорисовывай кольца. Если кольца есть — сохрани их. НЕ добавляй новые украшения, которых не было на фото. "
                f"Размер: {img_size}. "
            )
            
            if mode == "retry":
                prompt += " Сделай ДРУГОЙ вариант. Не повторяй предыдущий результат. "
            elif mode == "boost":
                prompt += " Усиль обработку ЗНАЧИТЕЛЬНО. Изменения должны быть очень заметными. "
            
            if "horizon" in error_type:
                prompt += f"ОБЯЗАТЕЛЬНО выровняй горизонт. {what_is_wrong}"
            if "thirds" in error_type:
                prompt += f"ОБЯЗАТЕЛЬНО примени правило третей. {what_is_wrong}"
            if "distortion" in error_type:
                prompt += f"ОБЯЗАТЕЛЬНО исправь дисторсию. {what_is_wrong}"
            if "pose" in error_type:
                prompt += f"Улучши позу человека. {what_is_wrong}"
            if "lighting" in error_type:
                prompt += f"Исправь освещение. {what_is_wrong}"
            if "shadow" in error_type:
                if "художественный" not in what_is_wrong.lower():
                    prompt += f"ОБЯЗАТЕЛЬНО убери тень фотографа. {what_is_wrong}"
                else:
                    prompt += f"Сохрани художественную тень. {what_is_wrong}"
            if "cropping" in error_type:
                prompt += f"ОБЯЗАТЕЛЬНО обрежь лишнее по краям. {what_is_wrong}"
            if "framing" in error_type:
                prompt += f"Улучши фрейминг. {what_is_wrong}"
            if "fill_frame" in error_type:
                prompt += f"Улучши композицию. {what_is_wrong}"
            
            if wish and wish.lower() != "ок":
                prompt += f"Дополнительное пожелание: {wish}"
        
        result = generate_image(image_bytes, prompt)
        if result is None:
            await bot.send_message(chat_id, "😕 Не получилось с первого раза. Пробую ещё раз...")
            result = generate_image(image_bytes, prompt)
            if result is None:
                await bot.send_message(chat_id, "😕 Не удалось сгенерировать. Попробуй ещё раз.")
                return

        if check_diff and not wish and not is_flat_lay:
            try:
                original_img = Image.open(io_module.BytesIO(image_bytes))
                result_img = Image.open(io_module.BytesIO(result))
                diff = ImageChops.difference(original_img.resize(result_img.size), result_img)
                if diff.getbbox() is None:
                    gen_wish[user_id] = "ОБЯЗАТЕЛЬНО выровняй горизонт до идеально ровного."
                    await bot.send_message(chat_id, "🔄 Первая попытка не дала изменений. Пробую глубокое улучшение...")
                    await do_generation(user_id, chat_id, gen_type, check_diff=False)
                    return
            except Exception:
                pass

        try:
            img = Image.open(io_module.BytesIO(result))
            if max(img.size) > 1920:
                img.thumbnail((1920, 1920), Image.LANCZOS)
            buf = io_module.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            result = buf.getvalue()
        except Exception:
            pass

        # Списание генераций
        if mode != "retry":
            used = gen_used_count.get(user_id, 0)
            if used == 0:
                if gen_type == "free" and not (user_id == 456504792 and not test_mode):
                    free_generations[user_id] = free_generations.get(user_id, 0) + 1
                    _save_gen()
                elif gen_type == "paid":
                    paid_generations[user_id] = max(0, paid_generations.get(user_id, 0) - 1)
                    _save_gen()
                gen_used_count[user_id] = 1

        last_photo[user_id] = result
        
        format_name = dict(FORMATS).get(fmt, fmt)
        await bot.send_photo(chat_id, BufferedInputFile(result, filename="generated.jpg"),
            caption=f"✨ Вот результат!\nФормат: {format_name}",
            reply_markup=get_keyboard(user_id))

        # Кнопки после генерации
        if is_flat_lay:
            post_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Доработать Flat Lay", callback_data=f"flat_refine_{gen_type}_{user_id}")],
                [InlineKeyboardButton(text="🔄 Перегенерировать (бесплатно)", callback_data=f"gen_retry_{gen_type}_{user_id}")],
                [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                 InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
            ])
            await bot.send_message(chat_id, "Оцени результат или доработай:", reply_markup=post_kb)
        else:
            post_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Доработать результат", callback_data=f"gen_refine_{gen_type}_{user_id}")],
                [InlineKeyboardButton(text="🔄 Перегенерировать (бесплатно)", callback_data=f"gen_retry_{gen_type}_{user_id}")],
                [InlineKeyboardButton(text="⚡ Усилить (-1 ген.)", callback_data=f"gen_boost_menu_{gen_type}_{user_id}")],
                [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                 InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
            ])
            await bot.send_message(chat_id, "Оцени результат или попробуй ещё раз:", reply_markup=post_kb)
        
        gen_wish[user_id] = ""
        
    except Exception as e:
        logger.exception("Ошибка генерации")
        await bot.send_message(chat_id, "😕 Что-то пошло не так при генерации.")

# ===== СТАРТ =====
@dp.message(CommandStart())
async def handle_start(message: Message):
    _add_history(message.from_user.id, "start", "Запустил бота")
    user_mode[message.from_user.id] = "free"
    flat_lay_active[message.from_user.id] = False

    if message.from_user.id == 456504792 and not test_mode:
        await message.answer("👑 Админ-панель", reply_markup=ADMIN_KEYBOARD)
    else:
        await message.answer("👇 Выбери действие:", reply_markup=USER_KEYBOARD)
        
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    gen_left = 5 - free_generations.get(message.from_user.id, 0) + paid_generations.get(message.from_user.id, 0)
    await message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
        caption=(
            "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
            "📸 <b>Бесплатный анализ:</b> пришли фото — я найду ошибки композиции и покажу их прямо на снимке.\n\n"
            "✨ <b>Улучшение фото:</b> ИИ исправит композицию, свет, уберёт лишнее и дорисует края.\n\n"
            "✂️ <b>Редактор:</b> меняй формат, улучшай, ретушируй, стилизуй — все инструменты в одном месте.\n\n"
            "📷 <b>Flat Lay:</b> сфоткай предметы сверху — сделаю стильную композицию для Instagram.\n\n"
            "🎓 <b>Мини-курс (10 дней):</b> с проверкой каждого задания. Первый день — бесплатно.\n\n"
            "🎯 <b>Авторский разбор:</b> личный разбор до 5 фото с советами.\n\n"
            f"Присылай фото и начнём разбор! 👇\n\n💎 Осталось генераций: {gen_left}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
            [InlineKeyboardButton(text="📷 Flat Lay (предметная съёмка)", callback_data="flat_lay")],
            [InlineKeyboardButton(text="💎 Мои генерации", callback_data="my_balance")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
            [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
        ])
    )

# ===== КОМАНДЫ =====
@dp.message(Command("author"))
async def handle_author(message: Message):
    await message.answer(
        "📸 <b>Автор бота — Евгений Севостьянов</b>\n"
        "Фотограф, преподаватель мобильной фотографии.\n\n"
        "📷 Instagram: <a href='https://instagram.com/sevosphoto'>@sevosphoto</a>\n"
        "💬 Telegram: <a href='https://t.me/sevosphoto'>@sevosphoto</a>\n"
        "🌐 VK: <a href='https://vk.com/cevoc'>@cevoc</a>",
        parse_mode="HTML", disable_web_page_preview=True,
    )

@dp.message(Command("stats"))
async def handle_stats(message: Message):
    text = get_stats(message.from_user.id)
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("course"))
async def handle_course(message: Message):
    await handle_course_status_logic(message.from_user.id, message.chat.id)

@dp.message(Command("reset"))
async def handle_reset(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("Только автор.")
        return
    if os.path.exists("course_users.json"):
        os.remove("course_users.json")
        await message.answer("✅ Сброшено.")

@dp.message(Command("start_course"))
async def handle_force_start(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("Только автор.")
        return
    from course import activate_by_username
    activate_by_username("sevosphoto")
    user_mode[message.from_user.id] = "course"
    await message.answer("✅ Курс активирован.")

@dp.message(Command("test"))
async def handle_test(message: Message):
    global test_mode
    if message.from_user.id != 456504792:
        await message.answer("Только автор.")
        return
    test_mode = not test_mode
    if test_mode:
        await message.answer("🧪 Тестовый режим ВКЛ", reply_markup=USER_KEYBOARD)
    else:
        await message.answer("👑 Режим автора ВКЛ", reply_markup=ADMIN_KEYBOARD)

@dp.message(Command("done"))
async def handle_done(message: Message):
    user_id = message.from_user.id
    orders = _load_author_orders()
    for order in orders:
        if order["user_id"] == user_id and order["status"] == "paid" and len(order["photos"]) > 0:
            order["status"] = "ready"
            _save_author_orders(orders)
            await message.answer(f"✅ Принято {len(order['photos'])} фото. Я разберу их и пришлю результат в течение 24 часов.")
            _send_telegram_message(-1004468971541, f"🔔 Заказ готов!\nПользователь: {user_id}\nФото: {len(order['photos'])} шт")
            return
    await message.answer("У тебя нет активного заказа с фото. Сначала оплати авторский разбор и пришли фото.")

# ===== ОСНОВНЫЕ КНОПКИ =====
@dp.callback_query(F.data == "new_photo")
async def handle_new_photo(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "free"
    flat_lay_active[callback.from_user.id] = False
    await callback.message.answer("Присылай фото — жду! 📷")
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery):
    await callback.answer()
    user_mode[callback.from_user.id] = "free"
    flat_lay_active[callback.from_user.id] = False
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    gen_left = 5 - free_generations.get(callback.from_user.id, 0) + paid_generations.get(callback.from_user.id, 0)
    await callback.message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
        caption=(
            "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
            "📸 <b>Бесплатный анализ:</b> пришли фото — покажу ошибки композиции.\n\n"
            "✨ <b>Улучшение фото:</b> ИИ исправит композицию, свет, дорисует края.\n\n"
            "✂️ <b>Редактор:</b> формат, ретушь, стилизация — всё в одном месте.\n\n"
            "📷 <b>Flat Lay:</b> стильная предметная съёмка для Instagram.\n\n"
            "🎓 <b>Мини-курс (10 дней):</b> первый день бесплатно.\n\n"
            "🎯 <b>Авторский разбор:</b> личный разбор фото.\n\n"
            f"💎 Осталось генераций: {gen_left}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
            [InlineKeyboardButton(text="📷 Flat Lay (предметная съёмка)", callback_data="flat_lay")],
            [InlineKeyboardButton(text="💎 Мои генерации", callback_data="my_balance")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
            [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
        ])
    )

@dp.callback_query(F.data == "author_info")
async def handle_author_info(callback: CallbackQuery):
    await callback.message.answer("📸 <b>Евгений Севостьянов</b>\nФотограф, преподаватель.\nInstagram: @sevosphoto\nTelegram: @sevosphoto\nVK: @cevoc", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "my_balance")
async def handle_my_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    free_left = 5 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)
    total = free_left + paid_left
    
    text = (
        f"💎 <b>Мои генерации</b>\n\n"
        f"🆓 Бесплатных осталось: {free_left} из 5\n"
        f"⚡ Оплаченных осталось: {paid_left}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Всего: {total}</b>\n\n"
    )
    
    if total <= 0:
        text += "У тебя закончились генерации. Купи пакет:"
        await callback.message.answer(text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ 10 улучшений — 99 ₽", callback_data="buy_10_gen")],
                [InlineKeyboardButton(text="⚡ 30 улучшений — 249 ₽", callback_data="buy_30_gen")],
            ]))
    else:
        text += "Отлично! Можешь продолжать улучшать фото."
        await callback.message.answer(text, parse_mode="HTML")
    
    await callback.answer()

# ===== РЕДАКТОР =====
@dp.callback_query(F.data == "change_format")
async def handle_change_format(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_mode[user_id] = "change_format"
    flat_lay_active[user_id] = False  # ВАЖНО: сбрасываем Flat Lay
    await callback.message.answer(
        "✂️ <b>Редактор</b>\n\n"
        "Загрузи фото и работай без анализа: меняй формат под соцсети, улучшай, ретушируй, стилизуй.\n\n"
        "1 генерация.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="new_photo")]]))
    user_mode[user_id] = "change_format"

@dp.callback_query(F.data == "change_format_same")
async def handle_change_format_same(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото!")
        return
    warnings = change_format_warnings.get(user_id, 0)
    if warnings < 3:
        gen_left = 5 - free_generations.get(user_id, 0) + paid_generations.get(user_id, 0)
        change_format_warnings[user_id] = warnings + 1
        await callback.answer()
        await callback.message.answer(
            f"📐 Это потратит 1 генерацию.\n💎 Осталось: {gen_left}\n\nПродолжить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data=f"change_format_go_{user_id}")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="main_menu")]]))
        return
    await callback.answer()
    await callback.message.answer("Выбери формат:",
        reply_markup=format_keyboard("paid" if paid_generations.get(user_id, 0) > 0 else "free"))

@dp.callback_query(F.data.startswith("change_format_go_"))
async def handle_change_format_go(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await callback.answer()
    await callback.message.answer("Выбери формат:",
        reply_markup=format_keyboard("paid" if paid_generations.get(user_id, 0) > 0 else "free"))

# ===== АВТОРСКИЙ РАЗБОР =====
@dp.callback_query(F.data == "author_review")
async def handle_author_review(callback: CallbackQuery):
    await callback.answer()
    user_mode[callback.from_user.id] = "free"
    flat_lay_active[callback.from_user.id] = False
    await callback.message.answer(
        "🎯 <b>Авторский разбор фото</b>\n\n"
        "Я лично разберу твои фото — подробно, с советами.\n\n"
        "📷 Присылай до 5 фото по одному.\n"
        "⏱ Ответ до 24 часов\n"
        "💰 500 ₽",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]]))

@dp.callback_query(F.data == "pay_author_review")
async def handle_pay_author_review(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(500, "Авторский разбор фото", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Не удалось создать ссылку.")
        return
    await callback.message.answer("💳 <b>Авторский разбор — 500 ₽</b>\nНажми кнопку чтобы оплатить.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 500 ₽", url=link)]]))

# ===== ПОДДЕРЖКА =====
@dp.callback_query(F.data == "donate_menu")
async def handle_donate_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("💛 Выбери сумму:", reply_markup=donate_keyboard())

async def _handle_donate(callback: CallbackQuery, amount: int):
    await callback.answer()
    link = create_payment_link(amount, f"Поддержка проекта ({amount} ₽)", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Не удалось создать ссылку.")
        return
    await callback.message.answer(f"💛 <b>Поддержать на {amount} ₽</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=link)]]))

@dp.callback_query(F.data == "donate_100")
async def d100(c: CallbackQuery): await _handle_donate(c, 100)

@dp.callback_query(F.data == "donate_300")
async def d300(c: CallbackQuery): await _handle_donate(c, 300)

@dp.callback_query(F.data == "donate_500")
async def d500(c: CallbackQuery): await _handle_donate(c, 500)

@dp.callback_query(F.data == "buy_10_gen")
async def handle_buy_10_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(99, "Пакет 10 генераций", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer("⚡ <b>10 генераций — 99 ₽</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 99 ₽", url=link)]]))

@dp.callback_query(F.data == "buy_30_gen")
async def handle_buy_30_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(249, "Пакет 30 генераций", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer("⚡ <b>30 генераций — 249 ₽</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 249 ₽", url=link)],
        ]))

# ===== FLAT LAY =====
@dp.callback_query(F.data == "flat_lay")
async def handle_flat_lay(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_mode[user_id] = "flat_lay_format"
    flat_lay_active[user_id] = False  # Сбрасываем, пока не выбран стиль
    
    free_left = 5 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)
    total = free_left + paid_left
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📐 Исходный формат", callback_data=f"flatfmt_original_{user_id}")],
        [InlineKeyboardButton(text="📱 1:1 (квадрат)", callback_data=f"flatfmt_1_1_{user_id}")],
        [InlineKeyboardButton(text="📱 4:5 (Instagram пост)", callback_data=f"flatfmt_4_5_{user_id}")],
        [InlineKeyboardButton(text="📱 9:16 (сториз)", callback_data=f"flatfmt_9_16_{user_id}")],
    ])
    
    if total > 0:
        await callback.message.answer(
            f"📷 <b>Flat Lay (предметная съёмка)</b>\n\n"
            f"Сфоткай предметы сверху или под небольшим углом.\n"
            f"Я распознаю их и сделаю стильную композицию.\n\n"
            f"Что можно снять:\n"
            f"• ☕ Кофе и завтрак\n"
            f"• 💄 Косметику\n"
            f"• 📚 Книги и канцелярию\n"
            f"• 🍽️ Еду\n"
            f"• 💍 Украшения\n\n"
            f"💎 Генераций осталось: {total}\n\n"
            f"Выбери формат:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.answer(
            f"❌ <b>Генерации закончились</b>\n\n"
            f"Для предметной съёмки нужна 1 генерация.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ 10 улучшений — 99 ₽", callback_data="buy_10_gen")],
                [InlineKeyboardButton(text="⚡ 30 улучшений — 249 ₽", callback_data="buy_30_gen")],
            ])
        )

@dp.callback_query(F.data.startswith("flatfmt_"))
async def handle_flat_fmt(callback: CallbackQuery):
    parts = callback.data.split("_")
    # flatfmt_original_123456 (3 части: flatfmt, original, id)
    # flatfmt_1_1_123456 (4 части: flatfmt, 1, 1, id)
    if len(parts) < 3:
        await callback.answer("Ошибка данных")
        return
    
    if parts[1] == "original":
        fmt = "original"
        user_id = int(parts[2])
    else:
        fmt = parts[1] + "_" + parts[2]
        user_id = int(parts[3])
    
    gen_format[user_id] = fmt
    user_mode[user_id] = "flat_lay_photo"
    
    await callback.answer()
    await callback.message.answer("📷 Пришли фото предметов сверху!")

@dp.callback_query(F.data.startswith("flatstyle_"))
async def handle_flat_style(callback: CallbackQuery):
    parts = callback.data.split("_")
    # flatstyle_cozy_123456
    if len(parts) < 3:
        await callback.answer("Ошибка данных")
        return
    
    style = parts[1]
    user_id = int(parts[2])
    
    if style not in FLAT_LAY_PROMPTS:
        await callback.answer("Неизвестный стиль")
        return
    
    gen_wish[user_id] = FLAT_LAY_PROMPTS[style]
    flat_lay_active[user_id] = True
    flat_lay_style[user_id] = style
    
    if free_generations.get(user_id, 0) < 5:
        gen_type = "free"
    else:
        gen_type = "paid"
    
    await callback.answer("🎨 Применяю стиль...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("flat_custom_prompt_"))
async def handle_flat_custom_prompt(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[-1])
    
    user_mode[user_id] = "flat_custom_prompt"
    flat_lay_active[user_id] = True
    
    await callback.answer()
    await callback.message.answer(
        "✏️ Напиши свой промпт для Flat Lay.\n\n"
        "Например:\n"
        "• «На белом мраморе с золотыми украшениями»\n"
        "• «На чёрном фоне с дымом»\n"
        "• «В стиле новогодней открытки»"
    )

# ===== ДОРАБОТКА FLAT LAY =====
@dp.callback_query(F.data.startswith("flat_refine_"))
async def handle_flat_refine(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[2]
    user_id = int(parts[3])
    
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Что доработать?</b>\n\n"
        "Выбери инструмент — он применится к текущему Flat Lay.\n"
        "Каждая доработка тратит 1 генерацию.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Другой стиль", callback_data=f"flat_refine_style_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="📐 Сменить формат", callback_data=f"flat_refine_format_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✨ Улучшить композицию", callback_data=f"flat_refine_comp_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💡 Исправить свет", callback_data=f"flat_refine_light_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"flat_refine_custom_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"flat_back_{gen_type}_{user_id}")],
        ]))

@dp.callback_query(F.data.startswith("flat_refine_style_"))
async def handle_flat_refine_style(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    
    keyboard = []
    for style, name in FLAT_LAY_STYLES.items():
        keyboard.append([InlineKeyboardButton(
            text=name,
            callback_data=f"flat_restyle_{style}_{gen_type}_{user_id}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"flat_refine_{gen_type}_{user_id}")])
    
    await callback.message.answer(
        "🎨 <b>Выбери новый стиль:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("flat_restyle_"))
async def handle_flat_restyle(callback: CallbackQuery):
    parts = callback.data.split("_")
    style = parts[2]
    gen_type = parts[3]
    user_id = int(parts[4])
    
    if style not in FLAT_LAY_PROMPTS:
        await callback.answer("Неизвестный стиль")
        return
    
    gen_wish[user_id] = FLAT_LAY_PROMPTS[style]
    flat_lay_active[user_id] = True
    flat_lay_style[user_id] = style
    gen_used_count[user_id] = 0  # Чтобы списалась генерация
    
    await callback.answer("🎨 Применяю новый стиль...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("flat_refine_format_"))
async def handle_flat_refine_format(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 1:1 (квадрат)", callback_data=f"flat_chfmt_1_1_{gen_type}_{user_id}")],
        [InlineKeyboardButton(text="📱 4:5 (Instagram пост)", callback_data=f"flat_chfmt_4_5_{gen_type}_{user_id}")],
        [InlineKeyboardButton(text="📱 9:16 (сториз)", callback_data=f"flat_chfmt_9_16_{gen_type}_{user_id}")],
        [InlineKeyboardButton(text="📐 Исходный формат", callback_data=f"flat_chfmt_original_{gen_type}_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"flat_refine_{gen_type}_{user_id}")],
    ])
    
    await callback.message.answer("📐 Выбери новый формат:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("flat_chfmt_"))
async def handle_flat_chfmt(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 6:
        await callback.answer("Ошибка данных")
        return
    
    if parts[2] == "original":
        fmt = "original"
        gen_type = parts[3]
        user_id = int(parts[4])
    else:
        fmt = parts[2] + "_" + parts[3]
        gen_type = parts[4]
        user_id = int(parts[5])
    
    gen_format[user_id] = fmt
    gen_wish[user_id] = (
        f"Создай НОВУЮ КОМПОЗИЦИЮ Flat Lay под формат {fmt}. "
        f"ПОЛНОСТЬЮ перемешай предметы: измени расположение, порядок, углы. "
        f"Распредели предметы гармонично, чтобы заполнили весь кадр. "
        f"Сохрани общий стиль. "
        f"Сохрани все предметы с фото."
    )
    flat_lay_active[user_id] = True
    gen_used_count[user_id] = 0
    
    await callback.answer("📐 Меняю формат...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("flat_refine_comp_"))
async def handle_flat_refine_comp(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    
    gen_wish[user_id] = (
        "Создай НОВУЮ КОМПОЗИЦИЮ Flat Lay как из Pinterest. "
        "ПОЛНОСТЬЮ перемешай предметы: измени их расположение, порядок, углы, расстояния. "
        "Сгруппируй их по-новому. "
        "Добавь новые декоративные элементы в том же стиле. "
        "Сделай композицию ЗАМЕТНО лучше и интереснее. "
        "Сохрани все предметы с фото и общий стиль."
    )
    flat_lay_active[user_id] = True
    gen_used_count[user_id] = 0
    
    await callback.answer("✨ Улучшаю композицию...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("flat_refine_light_"))
async def handle_flat_refine_light(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    
    gen_wish[user_id] = (
        "ЗАМЕТНО измени освещение Flat Lay. "
        "Сделай свет теплее, мягче, объёмнее. "
        "Добавь интересные тени и блики. "
        "Сохрани все предметы с фото и общий стиль."
    )
    flat_lay_active[user_id] = True
    gen_used_count[user_id] = 0
    
    await callback.answer("💡 Исправляю свет...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("flat_refine_custom_"))
async def handle_flat_refine_custom(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    
    user_mode[user_id] = "flat_custom"
    flat_lay_active[user_id] = True
    
    await callback.answer()
    await callback.message.answer("✏️ Напиши пожелание для доработки:")

@dp.callback_query(F.data.startswith("flat_back_"))
async def handle_flat_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

# ===== ПЕРЕГЕНЕРАЦИЯ =====
@dp.callback_query(F.data.startswith("gen_retry_"))
async def handle_gen_retry(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[2]
    
    try:
        user_id = int(parts[3])
    except ValueError:
        await callback.answer("Ошибка данных")
        return
    
    if gen_retry_count.get(user_id, 0) >= 1:
        await callback.answer("Лимит перегенераций исчерпан.", show_alert=True)
        return
    
    # Для Flat Lay — берём исходное фото
    # Для обычных — исходное
    if user_id in original_photo:
        last_photo[user_id] = original_photo[user_id]
    
    gen_retry_count[user_id] = 1
    
    await callback.answer("🔄 Генерирую другой вариант...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False, mode="retry")

# ===== КНОПКИ ГЕНЕРАЦИИ =====
@dp.callback_query(F.data == "gen_free")
async def handle_gen_free(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != 456504792 and free_generations.get(user_id, 0) >= 5:
        await callback.answer("Бесплатные генерации закончились. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото!")
        return
    await callback.answer()
    await callback.message.answer("✨ <b>Улучшение фото (бесплатно)</b>\n\nВыбери формат:", parse_mode="HTML", reply_markup=format_keyboard("free"))

@dp.callback_query(F.data == "gen_paid")
async def handle_gen_paid(callback: CallbackQuery):
    user_id = callback.from_user.id
    if paid_generations.get(user_id, 0) <= 0:
        await callback.answer("Нет оплаченных генераций. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото!")
        return
    await callback.answer()
    await callback.message.answer(f"✨ <b>Улучшение фото</b>\n\nОсталось: {paid_generations.get(user_id, 0)}\n\nВыбери формат:", parse_mode="HTML", reply_markup=format_keyboard("paid"))

# ===== ОБРАБОТКА ФОТО =====
@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"
    image = download_and_resize(photo_url, target_width=1024)
    image_bytes = image_to_bytes(image)
    
    last_photo[user_id] = image_bytes
    original_photo[user_id] = image_bytes
    gen_retry_count[user_id] = 0
    gen_used_count[user_id] = 0

    # Custom prompt для обычной генерации
    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "free"
        return

    # Custom prompt для Flat Lay
    if mode == "flat_custom":
        gen_wish[user_id] = message.text if hasattr(message, 'text') else ""
        gen_type = "free" if free_generations.get(user_id, 0) < 5 else "paid"
        await do_generation(user_id, message.chat.id, gen_type, check_diff=False)
        user_mode[user_id] = "free"
        return

    # Редактор — выбор формата
    if mode == "change_format":
        await message.answer("Выбери формат:",
            reply_markup=format_keyboard("paid" if paid_generations.get(user_id, 0) > 0 else "free"))
        return

    # Стилизация — выбор стиля
    if mode == "style_photo":
        keyboard = []
        for i in range(0, len(MAIN_STYLES), 2):
            row = []
            for style in MAIN_STYLES[i:i+2]:
                row.append(InlineKeyboardButton(
                    text=ALL_STYLES[style],
                    callback_data=f"gen_style_{style}_free_{user_id}"
                ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="✨ Ещё стили...", callback_data=f"gen_style_more_free_{user_id}")])
        
        await message.answer(
            "🎨 <b>Выбери стиль:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        return

    # Flat Lay — выбор стиля
    if mode == "flat_lay_photo":
        keyboard = []
        for style, name in FLAT_LAY_STYLES.items():
            keyboard.append([InlineKeyboardButton(
                text=name,
                callback_data=f"flatstyle_{style}_{user_id}"
            )])
        keyboard.append([InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"flat_custom_prompt_{user_id}")])
        
        await message.answer(
            "🎨 <b>Выбери стиль оформления:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        return

    # Проверка активного заказа на авторский разбор
    orders = _load_author_orders()
    active_order = None
    for order in orders:
        if order["user_id"] == user_id and order["status"] == "paid" and len(order["photos"]) < 5:
            active_order = order
            break
            
    if active_order and (not active_order.get("username") or active_order["username"].startswith("id")):
        active_order["username"] = message.from_user.username or f"id{user_id}"
    
    if active_order:
        photo_index = len(active_order["photos"])
        filename = _save_author_photo(active_order["time"], photo_index, image_bytes)
        active_order["photos"].append(filename)
        photo_count = len(active_order["photos"])
        if photo_count >= 5:
            active_order["status"] = "ready"
        _save_author_orders(orders)
        if photo_count >= 5:
            await message.answer("✅ Все 5 фото получены! Разберу в течение 24 часов и напишу тебе лично.")
            _send_telegram_message(-1004468971541, f"🔔 Заказ готов!\n<a href='tg://user?id={user_id}'>👤 Пользователь</a>\nФото: {photo_count} шт")
        else:
            await message.answer(
                f"📸 Фото получено ({photo_count} из 5). Можешь прислать ещё или нажать «Готово».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Готово — отправить на разбор", callback_data=f"author_ready_{user_id}")]]))
        return

    # Обычный анализ фото
    processing_msg = await message.answer("🔍 Анализирую кадр...")

    try:
        course_topic = None
        effective_has_access = has_access(user_id) and not (user_id == 456504792 and test_mode)
        if effective_has_access and user_mode.get(user_id) == "course":
            from course import get_current_topic
            course_topic = get_current_topic(user_id)

        result = analyze_photo(image_bytes, course_topic=course_topic)

        if result is not None:
            error_type = result.get("error_type", "unknown")
            last_analysis[user_id] = result
            add_analysis(user_id, error_type)
            _add_history(user_id, "analysis", f"Ошибки: {error_type}")

        if result is None:
            await processing_msg.edit_text("😕 Не смог разобрать, попробуй другое фото.")
            return

        drawings = result.get("drawings", [])
        annotated_image = draw_hints(image, drawings)
        annotated_bytes = image_to_bytes(annotated_image)
        await message.answer_photo(BufferedInputFile(annotated_bytes, filename="analysis.jpg"))

        caption = (
            f"📸 {result.get('title', 'Разбор кадра')}\n\n"
            f"❌ Что не так: {result.get('what_is_wrong', '---')}\n\n"
            f"🔄 Как исправить: {result.get('how_to_fix', '---')}\n\n"
            f"✨ Совет от профи: {result.get('pro_tip', '---')}\n\n"
            f"👍 Что хорошо: {result.get('praise', '---')}\n\n"
            f"🔴 красный — проблема\n🟢 зелёный — правильно\n🟡 жёлтый — внимание"
        )
        await message.answer(caption, reply_markup=get_keyboard(user_id))

        # Приглашение на курс
        from stats import _load_stats
        stats = _load_stats()
        total = stats.get(str(user_id), {}).get("total", 0)
        if total > 0 and total % 5 == 0:
            invites = {5: "📸 5 анализов! Мини-курс: 10 дней. 🎓", 10: "🔍 10 анализов! Мини-курс поможет. 🚀", 15: "🔥 15 анализов! Мини-курс — и ошибки уйдут. 🎓"}
            invite_text = invites.get(total, f"📸 {total} анализов! Мини-курс. 🎓")
            await asyncio.sleep(1)
            await message.answer(invite_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎓 Мини-курс — бесплатно", callback_data="start_trial")]]))

        # Проверка задания курса
        if has_access(user_id) and user_mode.get(user_id) == "course":
            status = get_status(user_id)
            if status is not None and "День" in status:
                add_photo(user_id)
                check_text = check_day(user_id, result)
                if check_text:
                    if _is_trial(user_id) and "задание выполнено" in check_text.lower():
                        link = create_payment_link(490, "Оплата за мини-курс", user_id) or "https://t.me/moy_razbor_bot"
                        check_text += "\n\n🎉 Пробный день пройден!\n💳 Оплати 490 ₽ и продолжай!"
                        await message.answer(check_text, parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Оплатить 490 ₽", url=link)]]))
                    else:
                        await message.answer(check_text, parse_mode="HTML")
                        if "задание выполнено" in check_text.lower():
                            await asyncio.sleep(1)
                            status = get_status(user_id)
                            if status:
                                await message.answer(status, parse_mode="HTML")
                                users = _load_users()
                                uid = next((k for k, d in users.items() if isinstance(d, dict) and d.get("username") == str(user_id)), str(user_id))
                                if uid in users:
                                    await send_photos(message.chat.id, users[uid].get("day", 1))
        await processing_msg.delete()
    except Exception:
        logger.exception("Ошибка при обработке фото")
        await processing_msg.edit_text("😕 Что-то пошло не так.")

# ===== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =====
@dp.message(~F.photo)
async def handle_non_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")
    text = message.text
    
    # Custom prompt для обычной генерации
    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_wish[user_id] = text
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "free"
        return

    # Custom prompt для Flat Lay
    if mode in ("flat_custom", "flat_custom_prompt"):
        gen_wish[user_id] = text
        gen_type = "free" if free_generations.get(user_id, 0) < 5 else "paid"
        flat_lay_active[user_id] = True
        await do_generation(user_id, message.chat.id, gen_type, check_diff=False)
        user_mode[user_id] = "free"
        return

    # Админские кнопки
    if text == "📊 Админка":
        await message.answer("📊 <b>Админ-панель</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_menu_stats")],
                [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin_menu_users")],
                [InlineKeyboardButton(text="💎 Генерации", callback_data="admin_menu_gen")],
                [InlineKeyboardButton(text="🎓 Курс", callback_data="admin_menu_course")],
                [InlineKeyboardButton(text="📝 Фидбек", callback_data="admin_menu_feedback")],
            ]))
        return

    if text == "🎫 Промо":
        await message.answer("🎫 <b>Промокоды</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать", callback_data="promo_menu_create")],
                [InlineKeyboardButton(text="📋 Список", callback_data="promo_menu_list")],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data="promo_menu_delete")],
                [InlineKeyboardButton(text="🔄 Сбросить", callback_data="promo_menu_reset")],
            ]))
        return

    if text == "📸 Заказы":
        message.text = "/admin orders"
        await handle_admin(message)
        return
    
    if text == "🧪 Тест":
        await handle_test(message)
        return
    
    if text == "🔄 Сброс курса":
        await handle_reset(message)
        return
    
    if text == "📋 Старт":
        await handle_start(message)
        return

    # Промокоды
    if mode == "promo_create_name":
        user_mode[user_id] = "promo_create_value"
        gen_wish[user_id] = text.upper()
        await message.answer(f"Название: <b>{text.upper()}</b>\n\nТеперь введи количество генераций или <b>course</b>:", parse_mode="HTML")
        return

    if mode == "promo_create_value":
        code = gen_wish.get(user_id, "CODE").upper()
        if text.lower() == "course":
            ptype, amount = "course", 0
            type_text = "🎓 Курс"
        else:
            try:
                amount = int(text)
                ptype = "gen"
                type_text = f"⚡ {amount} ген."
            except ValueError:
                await message.answer("❌ Введи число или слово 'course'")
                return
        promo = _load_promo()
        promo[code] = {"type": ptype, "amount": amount, "used_by": []}
        _save_promo(promo)
        user_mode[user_id] = "free"
        await message.answer(f"✅ Промокод <b>{code}</b> создан — {type_text}", parse_mode="HTML")
        return

    if mode == "promo_delete":
        code = text.upper()
        promo = _load_promo()
        if code in promo:
            del promo[code]
            _save_promo(promo)
            await message.answer(f"🗑 Промокод <b>{code}</b> удалён", parse_mode="HTML")
        else:
            await message.answer(f"❌ Код <b>{code}</b> не найден", parse_mode="HTML")
        user_mode[user_id] = "free"
        return

    if mode == "promo_reset":
        code = text.upper()
        promo = _load_promo()
        if code in promo:
            promo[code]["used_by"] = []
            _save_promo(promo)
            await message.answer(f"🔄 Промокод <b>{code}</b> сброшен", parse_mode="HTML")
        else:
            await message.answer(f"❌ Код <b>{code}</b> не найден", parse_mode="HTML")
        user_mode[user_id] = "free"
        return
    
    # Пользовательские кнопки
    if text == "📸 Анализ фото":
        user_mode[user_id] = "free"
        flat_lay_active[user_id] = False
        await message.answer("Присылай фото — я проанализирую композицию! 📷")
        return
    
    if text == "✂️ Редактор":
        user_mode[user_id] = "change_format"
        flat_lay_active[user_id] = False  # Сбрасываем Flat Lay
        await message.answer(
            "✂️ <b>Редактор</b>\n\n"
            "Загрузи фото и работай без анализа: меняй формат, улучшай, ретушируй, стилизуй.\n"
            "1 генерация.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="new_photo")]]))
        return

    if text == "📷 Flat Lay":
        user_mode[user_id] = "flat_lay_format"
        flat_lay_active[user_id] = False
        free_left = 5 - free_generations.get(user_id, 0)
        paid_left = paid_generations.get(user_id, 0)
        total = free_left + paid_left
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 1:1 (квадрат)", callback_data=f"flatfmt_1_1_{user_id}")],
            [InlineKeyboardButton(text="📱 4:5 (Instagram пост)", callback_data=f"flatfmt_4_5_{user_id}")],
            [InlineKeyboardButton(text="📱 9:16 (сториз)", callback_data=f"flatfmt_9_16_{user_id}")],
            [InlineKeyboardButton(text="📐 Исходный формат", callback_data=f"flatfmt_original_{user_id}")],
        ])
        
        if total > 0:
            await message.answer(
                f"📷 <b>Flat Lay (предметная съёмка)</b>\n\n"
                f"Сфоткай предметы сверху или под небольшим углом.\n"
                f"Я распознаю их и сделаю стильную композицию.\n\n"
                f"💎 Генераций осталось: {total}\n\n"
                f"Выбери формат:",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                f"❌ <b>Генерации закончились</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚡ 10 улучшений — 99 ₽", callback_data="buy_10_gen")],
                    [InlineKeyboardButton(text="⚡ 30 улучшений — 249 ₽", callback_data="buy_30_gen")],
                ])
            )
        return

    if text == "🎨 Стилизация":
        user_mode[user_id] = "style_photo"
        flat_lay_active[user_id] = False
        await message.answer("🎨 Пришли фото для стилизации.", parse_mode="HTML")
        return
    
    if text == "🏠 Главное меню":
        user_mode[user_id] = "free"
        flat_lay_active[user_id] = False
        PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
        gen_left = 5 - free_generations.get(user_id, 0) + paid_generations.get(user_id, 0)
        await message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
            caption=(
                "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
                "📸 <b>Бесплатный анализ:</b> пришли фото.\n\n"
                "✂️ <b>Редактор:</b> формат, ретушь, стилизация.\n\n"
                "📷 <b>Flat Lay:</b> предметная съёмка.\n\n"
                "🎓 <b>Мини-курс:</b> первый день бесплатно.\n\n"
                f"💎 Осталось генераций: {gen_left}"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
                [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
                [InlineKeyboardButton(text="📷 Flat Lay (предметная съёмка)", callback_data="flat_lay")],
                [InlineKeyboardButton(text="💎 Мои генерации", callback_data="my_balance")],
                [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
                [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
                [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
                [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
            ]))
        return
        
    if text == "🎓 Мини-курс":
        user_mode[user_id] = "course"
        flat_lay_active[user_id] = False
        await handle_course_status_logic(user_id, message.chat.id)
        return
    
    if text == "🎯 Авторский разбор":
        user_mode[user_id] = "free"
        flat_lay_active[user_id] = False
        await message.answer("🎯 <b>Авторский разбор</b>\n\nЯ лично разберу твои фото.\n📷 До 5 фото\n💰 500 ₽", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]]))
        return

    await message.answer("Пришли мне фотографию 📷")

# ===== ЕЖЕДНЕВНЫЙ ОТЧЁТ =====
async def daily_report():
    await asyncio.sleep(5)
    while True:
        now = datetime.now()
        target = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if now > target:
            target = target.replace(day=now.day + 1)
        await asyncio.sleep((target - now).total_seconds())
        
        history = _load_history()
        today = datetime.now().strftime("%d.%m.%Y")
        new_users = sum(1 for entries in history.values() for e in entries if today in e.get("time","") and e.get("action")=="start")
        analyses = sum(1 for entries in history.values() for e in entries if today in e.get("time","") and e.get("action")=="analysis")
        try:
            await bot.send_message(-1004468971541, f"📊 <b>{today}</b>\n👤 Новых: {new_users}\n📸 Анализов: {analyses}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отчёта: {e}")

# ===== ЗАПУСК =====
async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    asyncio.create_task(daily_report())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
