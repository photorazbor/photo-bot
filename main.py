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
from stats import add_analysis, get_stats, add_history as stats_add_history
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
        [KeyboardButton(text="🎨 Стилизация"), KeyboardButton(text="🎯 Авторский разбор")],
        [KeyboardButton(text="🎓 Мини-курс"), KeyboardButton(text="🏠 Главное меню")],
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
gen_wish = {}
gen_format = {}
gen_retry_count = {}
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
    """Добавляет запись в историю"""
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
                        asyncio.run_coroutine_threadsafe(bot.send_message(uid, "✅ Оплата получена! Присылай до 5 фото по одному (не файлом, а как обычное фото из галереи). Когда закончишь — нажми кнопку «Готово». После разбора я напишу тебе лично. Если я не смогу тебя найти — напиши мне @sevosphoto"), MAIN_LOOP)
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

async def do_generation(user_id: int, chat_id: int, gen_type: str, check_diff: bool = True):
    """Выполняет генерацию изображения на основе последнего фото"""
    if user_id not in last_photo:
        await bot.send_message(chat_id, "Сначала пришли фото для анализа!")
        return
    
    fmt = gen_format.get(user_id, "1_1")
    wish = gen_wish.get(user_id, "")
    image_bytes = last_photo[user_id]
    
    if wish and wish.lower() != "ок":
        await bot.send_message(chat_id, "🎨 Генерирую изображение по твоему пожеланию...")
    else:
        await bot.send_message(chat_id, "🎨 Генерирую изображение на основе анализа...")
    
    try:
        img_size = get_size_for_format(fmt, image_bytes)
        analysis = last_analysis.get(user_id, {})
        error_type = analysis.get("error_type", "")
        what_is_wrong = analysis.get("what_is_wrong", "")
        how_to_fix = analysis.get("how_to_fix", "")
        
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
            f"Размер: {img_size}. "
        )
        
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

        if check_diff and not wish:
            try:
                original_img = Image.open(io_module.BytesIO(image_bytes))
                result_img = Image.open(io_module.BytesIO(result))
                diff = ImageChops.difference(original_img.resize(result_img.size), result_img)
                if diff.getbbox() is None:
                    gen_wish[user_id] = "ОБЯЗАТЕЛЬНО выровняй горизонт до идеально ровного. Найди линию горизонта и поверни фото. Убери весь мусор. Сделай кадр чистым."
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

        # Списание генераций (только один раз, не для перегенерации)
        retries = gen_retry_count.get(user_id, 0)
        if retries == 0:
            if gen_type == "free" and not (user_id == 456504792 and not test_mode):
                free_generations[user_id] = free_generations.get(user_id, 0) + 1
                _save_gen()
            elif gen_type == "paid":
                paid_generations[user_id] = max(0, paid_generations.get(user_id, 0) - 1)
                _save_gen()
        gen_retry_count[user_id] = retries + 1

        # Обновляем last_photo для последующих доработок
        last_photo[user_id] = result
        
        format_name = dict(FORMATS).get(fmt, fmt)
        await bot.send_photo(chat_id, BufferedInputFile(result, filename="generated.jpg"),
            caption=f"✨ Вот твой улучшенный кадр!\nФормат: {format_name}",
            reply_markup=get_keyboard(user_id))

        # Кнопки для дальнейшей работы с результатом
        post_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Доработать результат", callback_data=f"gen_refine_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔄 Перегенерировать (бесплатно)", callback_data=f"gen_retry_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="⚡ Усилить (-1 ген.)", callback_data=f"gen_boost_menu_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
             InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
        ])
        await bot.send_message(chat_id, "Оцени результат или попробуй ещё раз:", reply_markup=post_kb)
        
        # Сбрасываем wish после генерации
        gen_wish[user_id] = ""
        
    except Exception as e:
        logger.exception("Ошибка генерации")
        await bot.send_message(chat_id, "😕 Что-то пошло не так при генерации.")

# ===== ОБРАБОТЧИКИ КОМАНД =====
@dp.message(CommandStart())
async def handle_start(message: Message):
    _add_history(message.from_user.id, "start", "Запустил бота")

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
            "🎓 <b>Мини-курс по композиции (10 дней):</b> с проверкой каждого задания. Первый день — бесплатно.\n\n"
            f"Присылай фото и начнём разбор! 👇\n\n💎 Осталось генераций: {gen_left}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
            [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
        ])
    )

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

@dp.callback_query(F.data.startswith("author_ready_"))
async def handle_author_ready(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    orders = _load_author_orders()
    for order in orders:
        if order["user_id"] == user_id and order["status"] == "paid" and len(order["photos"]) > 0:
            order["status"] = "ready"
            _save_author_orders(orders)
            await callback.message.edit_text(f"✅ Принято {len(order['photos'])} фото. Разберу в течение 24 часов и напишу тебе лично. Если не смогу найти — напиши мне @sevosphoto")
            _send_telegram_message(-1004468971541, f"🔔 Заказ готов!\nПользователь: {user_id}\nФото: {len(order['photos'])} шт")
            return
    await callback.answer("Нет активного заказа.")

# ===== ГЕНЕРАЦИЯ С ФОРМАТАМИ =====
def register_format_handlers():
    for fmt, name in FORMATS:
        def make_free_handler(fmt=fmt, name=name):
            @dp.callback_query(F.data == f"gen_{fmt}_free")
            async def handler(callback: CallbackQuery):
                user_id = callback.from_user.id
                gen_format[user_id] = fmt
                await callback.answer()
                await callback.message.answer(
                    f"✨ Выбран формат: <b>{name}</b>\n\nЧто делаем?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✨ Улучшить", callback_data=f"gen_go_ok_free_{user_id}")],
                        [InlineKeyboardButton(text="🔍 Глубокое улучшение", callback_data=f"gen_go_deep_free_{user_id}")],
                        [InlineKeyboardButton(text="🎨 Полная переработка", callback_data=f"gen_go_full_free_{user_id}")],
                        [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_go_pose_free_{user_id}")],
                        [InlineKeyboardButton(text="🔄 Поменять позу", callback_data=f"gen_go_repose_free_{user_id}")],
                        [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_go_retouch_free_{user_id}")],
                        [InlineKeyboardButton(text="📐 Выровнять горизонт", callback_data=f"gen_go_horizon_free_{user_id}")],
                        [InlineKeyboardButton(text="📐 Только формат", callback_data=f"gen_go_format_only_free_{user_id}")],
                        [InlineKeyboardButton(text="🎨 Стилизация", callback_data=f"gen_style_menu_full_free_{user_id}")],
                        [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_free_{user_id}")],
                    ]))
            return handler
        def make_paid_handler(fmt=fmt, name=name):
            @dp.callback_query(F.data == f"gen_{fmt}_paid")
            async def handler(callback: CallbackQuery):
                user_id = callback.from_user.id
                gen_format[user_id] = fmt
                await callback.answer()
                await callback.message.answer(
                    f"✨ Выбран формат: <b>{name}</b>\n\nЧто делаем?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✨ Улучшить", callback_data=f"gen_go_ok_paid_{user_id}")],
                        [InlineKeyboardButton(text="🔍 Глубокое улучшение", callback_data=f"gen_go_deep_paid_{user_id}")],
                        [InlineKeyboardButton(text="🎨 Полная переработка", callback_data=f"gen_go_full_paid_{user_id}")],
                        [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_go_pose_paid_{user_id}")],
                        [InlineKeyboardButton(text="🔄 Поменять позу", callback_data=f"gen_go_repose_paid_{user_id}")],
                        [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_go_retouch_paid_{user_id}")],
                        [InlineKeyboardButton(text="📐 Выровнять горизонт", callback_data=f"gen_go_horizon_paid_{user_id}")],
                        [InlineKeyboardButton(text="📐 Только формат", callback_data=f"gen_go_format_only_paid_{user_id}")],
                        [InlineKeyboardButton(text="🎨 Стилизация", callback_data=f"gen_style_menu_full_paid_{user_id}")],
                        [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_paid_{user_id}")],
                    ]))
            return handler
        make_free_handler()
        make_paid_handler()

register_format_handlers()

# ===== ОБРАБОТЧИКИ ДЕЙСТВИЙ ГЕНЕРАЦИИ =====
# ВАЖНО: порядок обработчиков! Специфичные сначала, общие потом.

@dp.callback_query(F.data.startswith("gen_go_ok_"))
async def handle_gen_go_ok(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Улучши фото: выровняй горизонт и вертикали, убери мусор, исправь свет и цвета. Сделай кадр заметно лучше."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_horizon_"))
async def handle_gen_go_horizon(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Только выровняй горизонт. Найди линию горизонта и поверни изображение так, чтобы она стала идеально горизонтальной. Это единственная задача. Не меняй объекты, свет, композицию. Просто поверни фото до ровного горизонта."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_format_only_"))
async def handle_gen_go_format_only(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 6:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[4]
    user_id = int(parts[5])
    gen_wish[user_id] = "Только измени формат: дорисуй или обрежь края. НЕ меняй изображение."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_deep_"))
async def handle_gen_go_deep(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "ОБЯЗАТЕЛЬНО выровняй горизонт и вертикали. Убери весь мусор. Сделай кадр чистым."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_pose_"))
async def handle_gen_go_pose(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Сфокусируйся ТОЛЬКО на позе: сделай её изящнее. НЕ меняй фон и освещение."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_retouch_"))
async def handle_gen_go_retouch(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Сделай полную профессиональную ретушь: выровняй тон кожи, сделай его гладким и сияющим. Полностью убери тёмные круги под глазами, разгладь все морщины и складки на лице и шее. Убери горизонтальные полоски и кольцевые складки на шее. Уменьши двойной подбородок до минимума. Сделай причёску аккуратной, объёмной и ухоженной. Добавь выраженный студийный свет с мягкими тенями. Усиль контраст и резкость на лице. НЕ меняй позу, композицию, фон. Лицо должно выглядеть как после профессиональной фотосессии."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_repose_"))
async def handle_gen_go_repose(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Полностью измени позу: разверни корпус, измени положение рук и ног. Сохрани лицо."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_full_"))
async def handle_gen_go_full(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Полностью переработай кадр: позу, фон, свет. Сохрани лицо и одежду."
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"

@dp.callback_query(F.data.startswith("gen_go_custom_"))
async def handle_gen_go_custom(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer("Запускаю генерацию...")
    await callback.message.answer(
        "✏️ Напиши пожелание, например:\n"
        "• «убери провода и мусор»\n"
        "• «сделай свет мягче»\n"
        "• «дорисуй обрезанный край»\n"
        "• «добавь закатное небо»")

# ===== СТИЛИЗАЦИЯ - ВАЖНЫЙ ПОРЯДОК ОБРАБОТЧИКОВ =====

# 1. Сначала самое специфичное: gen_style_menu_full_ (6 частей)
@dp.callback_query(F.data.startswith("gen_style_menu_full_"))
async def handle_gen_style_menu_full(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_style_menu_full_free_123456
    # 0    1     2    3    4    5
    if len(parts) < 6:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[4]
    user_id = int(parts[5])
    await callback.answer()
    await callback.message.answer(
        "🎨 <b>Выбери стиль:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Ч/Б", callback_data=f"gen_style_bw_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="🌅 Закат", callback_data=f"gen_style_golden_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎞️ Плёнка", callback_data=f"gen_style_film_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="💡 Воздушный", callback_data=f"gen_style_highkey_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🌙 Драматичный", callback_data=f"gen_style_lowkey_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="🌸 Пастель", callback_data=f"gen_style_pastel_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🌈 Ретро 80-х", callback_data=f"gen_style_retro_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="🎬 Кино", callback_data=f"gen_style_cinema_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🖼️ Картина", callback_data=f"gen_style_painting_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="💥 Комикс", callback_data=f"gen_style_comics_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎌 Аниме", callback_data=f"gen_style_anime_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="🎨 Акварель", callback_data=f"gen_style_aquarel_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔥 Киберпанк", callback_data=f"gen_style_cyberpunk_{gen_type}_{user_id}"),
             InlineKeyboardButton(text="🖤 Нуар", callback_data=f"gen_style_noir_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"gen_boost_back_{gen_type}_{user_id}")],
        ]))

# 2. Затем gen_style_menu_ (5 частей) - для обратной совместимости
@dp.callback_query(F.data.startswith("gen_style_menu_"))
async def handle_gen_style_menu(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_style_menu_free_123456
    # 0    1     2    3    4
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    await callback.message.answer(
        "🎨 <b>Стилизация</b> (-1 генерация)\n\nВыбери стиль:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Ч/Б фотография", callback_data=f"gen_style_bw_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🌅 Золотой час", callback_data=f"gen_style_golden_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎞️ Под плёнку", callback_data=f"gen_style_film_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🖼️ Как картина", callback_data=f"gen_style_painting_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💡 Высокий ключ", callback_data=f"gen_style_highkey_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🌙 Низкий ключ", callback_data=f"gen_style_lowkey_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"gen_go_back_{gen_type}_{user_id}")],
        ]))

# 3. Конкретный стиль (gen_style_bw_free_123456)
@dp.callback_query(F.data.startswith("gen_style_"))
async def handle_gen_style(callback: CallbackQuery):
    # Пропускаем menu вызовы
    if "menu" in callback.data:
        return
    
    parts = callback.data.split("_")
    # gen_style_bw_free_123456
    # 0    1     2   3    4
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    
    style = parts[2]
    gen_type = parts[3]
    user_id = int(parts[4])
    
    styles = {
        "bw": "Переведи фото в чёрно-белый стиль. Сделай контрастным и атмосферным. НЕ меняй позу, композицию.",
        "golden": "Добавь эффект закатного солнца: тёплый вечерний свет, мягкие тени, золотистые оттенки. НЕ меняй позу, композицию.",
        "film": "Сделай фото в стиле плёночной фотографии: зернистость, мягкие тона, винтажный вид. НЕ меняй позу, композицию.",
        "highkey": "Сделай фото воздушным: светлые тона, минимум теней, лёгкий стиль. НЕ меняй позу, композицию.",
        "lowkey": "Сделай фото драматичным: тёмные тона, глубокие тени, контрастный свет. НЕ меняй позу, композицию.",
        "pastel": "Добавь пастельные тона: мягкие розовые, голубые, кремовые оттенки. Нежный воздушный стиль. НЕ меняй позу, композицию.",
        "retro": "Сделай фото в стиле ретро 80-х: VHS-эффект, выцветшие цвета, зернистость, лёгкая неоновая дымка. НЕ меняй позу, композицию.",
        "cinema": "Сделай фото кинематографичным: широкий кадр, глубокая цветокоррекция, мягкий контраст, атмосфера фильма. НЕ меняй позу, композицию.",
        "painting": "Преврати фото в картину: имитация живописи, мазки кисти, художественный стиль. НЕ меняй позу, композицию.",
        "comics": "Преврати фото в комикс: яркие цвета, чёткие контуры, стиль графического романа. НЕ меняй позу, композицию.",
        "anime": "Преврати фото в аниме: стиль японской анимации, большие глаза, мягкие линии, яркие цвета. НЕ меняй позу, композицию.",
        "aquarel": "Преврати фото в акварель: мягкие разводы краски, лёгкие полупрозрачные тона, художественный стиль. НЕ меняй позу, композицию.",
        "cyberpunk": "Сделай фото в стиле киберпанк: неоновые огни, футуристическая атмосфера, яркие кислотные цвета, тёмный фон. НЕ меняй позу, композицию.",
        "noir": "Сделай фото в стиле нуар: чёрно-белый детектив, резкие тени, драматический свет, атмосфера 40-х. НЕ меняй позу, композицию.",
    }
    
    wish = styles.get(style, "Примени художественный стиль.")
    gen_wish[user_id] = wish
    user_mode[user_id] = f"gen_wish_{gen_type}"
    gen_format[user_id] = "original"
    
    # ВАЖНО: убрано дублирование списания генераций!
    # do_generation сам спишет генерацию
    
    await callback.answer(f"🎨 Применяю стиль...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"

# ===== УСИЛЕНИЕ - ВАЖНЫЙ ПОРЯДОК ОБРАБОТЧИКОВ =====

# 1. Сначала gen_boost_back_ (назад)
@dp.callback_query(F.data.startswith("gen_boost_back_"))
async def handle_gen_boost_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

# 2. Затем gen_boost_menu_ (меню)
@dp.callback_query(F.data.startswith("gen_boost_menu_"))
async def handle_gen_boost_menu(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_boost_menu_free_123456
    # 0    1     2    3    4
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    await callback.message.answer(
        "⚡ <b>Усилить обработку</b> (-1 генерация)\n\nЧто усилить?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📐 Исправить горизонт", callback_data=f"gen_boost_horizon_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🧹 Чистка фона", callback_data=f"gen_boost_clean_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💡 Свет", callback_data=f"gen_boost_light_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_boost_pose_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎨 Полная переработка", callback_data=f"gen_boost_full_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_boost_retouch_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎨 Стилизация", callback_data=f"gen_style_menu_full_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"gen_boost_back_{gen_type}_{user_id}")],
        ]))

# 3. Конкретное усиление (gen_boost_horizon_free_123456)
@dp.callback_query(F.data.startswith("gen_boost_"))
async def handle_gen_boost(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_boost_horizon_free_123456
    # 0    1     2      3    4
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    
    boost_type = parts[2]
    gen_type = parts[3]
    user_id = int(parts[4])
    
    boosts = {
        "horizon": "САМОЕ ГЛАВНОЕ: выровняй горизонт. Найди линию горизонта и поверни изображение так, чтобы она стала идеально горизонтальной. Дорисуй недостающие края после поворота. НЕ меняй объекты, свет, композицию.",
        "clean": "Убери ВЕСЬ мусор, грязь, провода, случайные объекты с фона и земли. Сделай кадр идеально чистым. НЕ меняй главный объект.",
        "light": "Полностью переработай освещение: убери пересветы, осветли тени, сделай свет объёмным и контрастным. Улучши цвета — сделай их сочнее.",
        "pose": "Сделай позу значительно изящнее: выпрями осанку, разверни корпус, измени положение рук и ног. НЕ меняй лицо.",
        "full": "Сделай полную переработку кадра: выровняй горизонт, убери весь мусор, исправь свет, улучши позу, почисти фон. Оставь только главный объект и сделай кадр идеальным.",
        "retouch": "Сделай полную профессиональную ретушь: выровняй тон кожи, сделай его гладким и сияющим. Полностью убери тёмные круги под глазами, разгладь все морщины и складки на лице и шее. Убери горизонтальные полоски и кольцевые складки на шее. Уменьши двойной подбородок до минимума. Сделай причёску аккуратной, объёмной и ухоженной. Добавь выраженный студийный свет с мягкими тенями. Усиль контраст и резкость на лице. НЕ меняй позу, композицию, фон. Лицо должно выглядеть как после профессиональной фотосессии.",
    }
    
    wish = boosts.get(boost_type, "Улучши фото")
    gen_wish[user_id] = wish
    
    # ВАЖНО: убрано дублирование списания генераций!
    # do_generation сам спишет генерацию
    
    await callback.answer(f"⚡ Усиливаю...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)

# ===== ДОРАБОТКА РЕЗУЛЬТАТА =====
@dp.callback_query(F.data.startswith("gen_refine_"))
async def handle_gen_refine(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_refine_free_123456
    # 0    1     2    3
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[2]
    user_id = int(parts[3])
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Доработать результат</b>\n\n"
        "Выбери инструмент — он применится к улучшенному фото.\n"
        "Каждая доработка тратит 1 генерацию.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_go_pose_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔄 Поменять позу", callback_data=f"gen_go_repose_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_go_retouch_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🎨 Стилизация", callback_data=f"gen_style_menu_full_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="📐 Только формат", callback_data=f"gen_go_format_only_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_{gen_type}_{user_id}")],
        ]))

# ===== ПЕРЕГЕНЕРАЦИЯ =====
@dp.callback_query(F.data.startswith("gen_retry_"))
async def handle_gen_retry(callback: CallbackQuery):
    parts = callback.data.split("_")
    # gen_retry_free_123456
    # 0    1     2    3
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[2]
    user_id = int(parts[3])
    
    if gen_retry_count.get(user_id, 0) >= 2:
        await callback.answer("Лимит перегенераций исчерпан.", show_alert=True)
        return
    
    await callback.answer("🔄 Генерирую заново...")
    await do_generation(user_id, callback.message.chat.id, gen_type)

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

# ===== НАЗАД =====
@dp.callback_query(F.data.startswith("gen_go_back_"))
async def handle_gen_go_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

# ===== ФИДБЕК =====
@dp.callback_query(F.data.startswith("fb_good_"))
async def handle_fb_good(callback: CallbackQuery):
    await callback.answer("Спасибо! 🙏")
    await callback.message.edit_text("👍 Спасибо за оценку!")

@dp.callback_query(F.data.startswith("fb_bad_"))
async def handle_fb_bad(callback: CallbackQuery):
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("Что не понравилось?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📐 Горизонт", callback_data=f"fb_reason_horizon_{user_id}")],
            [InlineKeyboardButton(text="🪵 Обрезка", callback_data=f"fb_reason_crop_{user_id}")],
            [InlineKeyboardButton(text="👤 Лицо", callback_data=f"fb_reason_face_{user_id}")],
            [InlineKeyboardButton(text="💡 Свет", callback_data=f"fb_reason_light_{user_id}")],
            [InlineKeyboardButton(text="📐 Поза", callback_data=f"fb_reason_pose_{user_id}")],
            [InlineKeyboardButton(text="✏️ Другое", callback_data=f"fb_reason_other_{user_id}")],
        ]))

@dp.callback_query(F.data.startswith("fb_reason_"))
async def handle_fb_reason(callback: CallbackQuery):
    await callback.answer("Записал! 🔧")
    parts = callback.data.split("_")
    reason = parts[2]
    user_id = int(parts[-1])
    _save_feedback({"user_id": user_id, "reason": reason, "time": datetime.now().isoformat()})
    await callback.message.edit_text("Спасибо! Я учту это. 📝")

# ===== ЛОГИКА КУРСА =====
def _is_trial(user_id: int) -> bool:
    users = _load_users()
    for key, data in users.items():
        if isinstance(data, dict) and data.get("username") == str(user_id):
            return data.get("trial", False)
    return False

async def handle_course_status_logic(user_id: int, chat_id: int):
    effective = has_access(user_id) and not (user_id == 456504792 and test_mode)
    if effective:
        user_mode[user_id] = "course"
        status = get_status(user_id)
        if status:
            if "День 0" in status or "Подготовка" in status:
                await bot.send_message(chat_id, status, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")]]))
                await send_photos(chat_id, 0)
            elif "День 1" in status and _is_trial(user_id):
                await bot.send_message(chat_id, status + "\n\n🆓 Это твой бесплатный день!", parse_mode="HTML")
                await send_photos(chat_id, 1)
            else:
                await bot.send_message(chat_id, status, parse_mode="HTML")
                users = _load_users()
                uid = next((k for k, d in users.items() if isinstance(d, dict) and d.get("username") == str(user_id)), str(user_id))
                if uid in users:
                    await send_photos(chat_id, users[uid].get("day", 1))
        return
    await bot.send_message(chat_id,
        "🎓 <b>Мини-курс по композиции (10 дней)</b>\n\n"
        "10-дневный челлендж с проверкой заданий.\n"
        "🆓 День 0 и 1 — бесплатно!\n💰 Полный доступ: 490 ₽",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Начать бесплатно", callback_data="start_trial")],
            [InlineKeyboardButton(text="💳 Оплатить (490 ₽)", callback_data="pay_course")]]))

@dp.callback_query(F.data == "start_trial")
async def handle_start_trial(callback: CallbackQuery):
    await callback.answer()
    activate_free_trial(callback.from_user.id)
    user_mode[callback.from_user.id] = "course"
    status = get_status(callback.from_user.id)
    if status:
        await callback.message.answer(status, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")]]))
        await send_photos(callback.message.chat.id, 0)

@dp.callback_query(F.data == "pay_course")
async def handle_pay_course(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(490, "Оплата за мини-курс", callback.from_user.id) or "https://t.me/moy_razbor_bot"
    await callback.message.answer("💳 <b>Оплата курса — 490 ₽</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 490 ₽", url=link)]]))

@dp.callback_query(F.data == "course_status")
async def handle_course_status(callback: CallbackQuery):
    await callback.answer()
    await handle_course_status_logic(callback.from_user.id, callback.message.chat.id)

@dp.callback_query(F.data == "start_course_btn")
async def handle_start_course_btn(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_mode[user_id] = "course"
    add_text = add_photo(user_id)
    if add_text:
        if _is_trial(user_id) and "День 1" in add_text:
            add_text += "\n\n🆓 Это твой бесплатный день!"
        await callback.message.answer(add_text, parse_mode="HTML")
        from course import get_next_day
        if get_next_day(user_id) == 1:
            await send_photos(callback.message.chat.id, 1)

@dp.callback_query(F.data == "mode_course")
async def handle_mode_course(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "course"
    await callback.answer("✅ Режим курса")

@dp.callback_query(F.data == "mode_free")
async def handle_mode_free(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "free"
    await callback.answer("🔍 Обычный анализ")

# ===== ОСНОВНЫЕ КНОПКИ =====
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

@dp.callback_query(F.data == "new_photo")
async def handle_retry_button(callback: CallbackQuery):
    await callback.message.answer("Присылай фото — жду! 📷")
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery):
    await callback.answer()
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    gen_left = 5 - free_generations.get(callback.from_user.id, 0) + paid_generations.get(callback.from_user.id, 0)
    await callback.message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
        caption=(
            "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
            "📸 <b>Бесплатный анализ:</b> пришли фото.\n\n"
            "✨ <b>Улучшение фото:</b> ИИ исправит композицию.\n\n"
            "✂️ <b>Редактор:</b> меняй формат, улучшай, ретушируй, стилизуй — все инструменты в одном месте.\n\n"
            "🎓 <b>Мини-курс (10 дней):</b> первый день бесплатно.\n\n"
            f"💎 Осталось генераций: {gen_left}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
            [InlineKeyboardButton(text="💎 Мои генерации", callback_data="my_balance")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
            [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
        ])
    )

@dp.callback_query(F.data == "change_format")
async def handle_change_format(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "✂️ <b>Редактор</b>\n\n"
        "Загрузи фото и работай без анализа: меняй формат под соцсети, улучшай, ретушируй, стилизуй, исправляй позу.\n\n"
        "Все инструменты будут доступны после выбора формата.\n"
        "1 генерация.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="new_photo")]]))
    user_mode[callback.from_user.id] = "change_format"
    
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

@dp.callback_query(F.data == "author_review")
async def handle_author_review(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎯 <b>Авторский разбор фото</b>\n\n"
        "Я лично разберу твои фото — подробно, с советами.\n\n"
        "📷 Присылай до 5 фото по одному (не файлом, а как обычное фото из галереи).\n"
        "⏱ Ответ до 24 часов\n"
        "💰 500 ₽\n\n"
        "После оплаты присылай фото в этот чат.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]]))

@dp.callback_query(F.data == "pay_author_review")
async def handle_pay_author_review(callback: CallbackQuery):
    await callback.answer()
    # ИСПРАВЛЕНО: цена 500 ₽ вместо 1 ₽
    link = create_payment_link(500, "Авторский разбор фото", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Не удалось создать ссылку.")
        return
    await callback.message.answer("💳 <b>Авторский разбор — 500 ₽</b>\nНажми кнопку чтобы оплатить.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 500 ₽", url=link)]]))

# ===== ПОДДЕРЖКА И ПОКУПКИ =====
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
            [InlineKeyboardButton(text="💳 Оплатить 249 ₽", url=link)]]))

# ===== АДМИН-ПАНЕЛЬ =====
@dp.message(Command("admin"))
async def handle_admin(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("⛔ Нет доступа.")
        return
    args = message.text.split()
    if len(args) == 1:
        await message.answer(
            "📊 <b>Админ-панель</b>\n\n"
            "/admin stats / users / history / gen / course / feedback / orders\n"
            "/admin reset_orders — сбросить заказы",
            parse_mode="HTML")
        return
    command = args[1].lower()
    if command == "reset_orders":
        _save_author_orders([])
        await message.answer("✅ Заказы сброшены")
        return
    if command == "stats":
        users = _load_users()
        history = _load_history()
        await message.answer(f"👤 Пользователей: {len(users)}\n📸 Анализов: {sum(d.get('total',0) for d in users.values())}")
    elif command == "users":
        users = _load_users()
        text = "\n".join(f"• {d.get('username', uid)} — {d.get('total',0)} фото" for uid, d in users.items())
        await message.answer(text or "Нет пользователей")
    elif command == "gen":
        text = "\n".join(f"• {uid}: {c} шт" for uid, c in paid_generations.items() if c > 0)
        await message.answer(text or "Нет оплаченных генераций")
    elif command == "course":
        users = _load_users()
        text = "\n".join(f"• {d.get('username', uid)}: день {d.get('day',0)}/10" for uid, d in users.items() if d.get('day',0) > 0)
        await message.answer(text or "Никто не начал")
    elif command == "feedback":
        if os.path.exists(FEEDBACK_FILE):
            with open(FEEDBACK_FILE) as f:
                fb = json.load(f)
            reasons = {"horizon": "📐", "crop": "🪵", "face": "👤", "light": "💡", "pose": "📐", "other": "✏️"}
            text = "\n".join(f"• {e['time'][:10]} — {reasons.get(e['reason'],'?')}" for e in fb[-20:])
            await message.answer(text or "Нет записей")
        else:
            await message.answer("Нет записей")
    elif command == "orders":
        orders = _load_author_orders()
        if not orders:
            await message.answer("📭 Нет заказов")
            return
        text = "📸 <b>Заказы:</b>\n\n"
        for i, o in enumerate(orders):
            s = "✅" if o["status"] == "ready" else ("⏳" if o["status"] == "paid" else "✔️")
            text += f"#{i} | {o['user_id']} | Фото: {len(o.get('photos',[]))} | {s}\n"
        text += "\n/admin order НОМЕР — посмотреть"
        await message.answer(text, parse_mode="HTML")
    elif command == "order" and len(args) >= 3:
        try:
            idx = int(args[2])
            orders = _load_author_orders()
            if idx < 0 or idx >= len(orders):
                await message.answer("❌ Неверный номер")
                return
            o = orders[idx]
            username = o.get("username", f"id{o['user_id']}")
            if username.startswith("id"):
                user_link = f"tg://user?id={o['user_id']}"
            else:
                user_link = f"https://t.me/{username}"
            await message.answer(f"📸 Заказ #{idx}\n<a href='{user_link}'>👤 Написать пользователю</a>\nСтатус: {o['status']}", parse_mode="HTML")
            for filename in o.get("photos", []):
                filepath = os.path.join(AUTHOR_PHOTOS_DIR, filename)
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        photo_bytes = f.read()
                    await message.answer_photo(BufferedInputFile(photo_bytes, filename=filename))
            await message.answer("Действия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Выполнен", callback_data=f"author_done_{idx}")],
            ]))
        except ValueError:
            await message.answer("❌ Номер должен быть числом")
    else:
        await message.answer("❌ Неизвестная команда")

@dp.callback_query(F.data.startswith("author_done_"))
async def handle_author_done(callback: CallbackQuery):
    idx = int(callback.data.split("_")[-1])
    orders = _load_author_orders()
    if idx < len(orders):
        orders[idx]["status"] = "done"
        _save_author_orders(orders)
        await callback.answer("✅ Отмечено!")
        await callback.message.edit_text(callback.message.text + "\n\n✅ Выполнен")

# ===== АДМИН-МЕНЮ (CALLBACK) =====
@dp.callback_query(F.data == "admin_menu_stats")
async def admin_menu_stats(callback: CallbackQuery):
    users = _load_users()
    await callback.message.answer(f"👤 Пользователей: {len(users)}\n📸 Анализов: {sum(d.get('total',0) for d in users.values())}")
    await callback.answer()

@dp.callback_query(F.data == "admin_menu_users")
async def admin_menu_users(callback: CallbackQuery):
    users = _load_users()
    text = "\n".join(f"• {d.get('username', uid)} — {d.get('total',0)} фото" for uid, d in users.items())
    await callback.message.answer(text or "Нет пользователей")
    await callback.answer()

@dp.callback_query(F.data == "admin_menu_gen")
async def admin_menu_gen(callback: CallbackQuery):
    text = "\n".join(f"• {uid}: {c} шт" for uid, c in paid_generations.items() if c > 0)
    await callback.message.answer(text or "Нет оплаченных генераций")
    await callback.answer()

@dp.callback_query(F.data == "admin_menu_course")
async def admin_menu_course(callback: CallbackQuery):
    users = _load_users()
    text = "\n".join(f"• {d.get('username', uid)}: день {d.get('day',0)}/10" for uid, d in users.items() if d.get('day',0) > 0)
    await callback.message.answer(text or "Никто не начал")
    await callback.answer()

@dp.callback_query(F.data == "admin_menu_feedback")
async def admin_menu_feedback(callback: CallbackQuery):
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE) as f:
            fb = json.load(f)
        reasons = {"horizon": "📐", "crop": "🪵", "face": "👤", "light": "💡", "pose": "📐", "other": "✏️"}
        text = "\n".join(f"• {e['time'][:10]} — {reasons.get(e['reason'],'?')}" for e in fb[-20:])
        await callback.message.answer(text or "Нет записей")
    else:
        await callback.message.answer("Нет записей")
    await callback.answer()

# ===== ПРОМОКОДЫ =====
@dp.message(Command("promo"))
async def handle_promo(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    if user_id == 456504792 and len(args) >= 2:
        action = args[1].lower()
        if action == "create" and len(args) >= 3:
            code = args[2].upper()
            if len(args) >= 4:
                if args[-1].lower() == "course":
                    ptype, amount = "course", 0
                else:
                    try:
                        amount, ptype = int(args[3]), "gen"
                    except ValueError:
                        await message.answer("❌ Количество должно быть числом")
                        return
            else:
                await message.answer("❌ Укажи количество или 'course'")
                return
            promo = _load_promo()
            promo[code] = {"type": ptype, "amount": amount, "used_by": []}
            _save_promo(promo)
            await message.answer(f"✅ Промокод {code} создан")
            return
        elif action == "list":
            promo = _load_promo()
            text = "\n".join(f"• {c}: {d['type']} {d['amount']}" for c, d in promo.items())
            await message.answer(text or "📭 Нет промокодов")
            return
        elif action == "delete" and len(args) >= 3:
            promo = _load_promo()
            if args[2].upper() in promo:
                del promo[args[2].upper()]
                _save_promo(promo)
                await message.answer("🗑 Удалён")
            return
        elif action == "reset" and len(args) >= 3:
            promo = _load_promo()
            if args[2].upper() in promo:
                promo[args[2].upper()]["used_by"] = []
                _save_promo(promo)
                await message.answer("🔄 Сброшен")
            return
    if len(args) == 2:
        code = args[1].upper()
        promo = _load_promo()
        if code not in promo:
            await message.answer("❌ Не существует")
            return
        d = promo[code]
        if user_id in d.get("used_by", []):
            await message.answer("❌ Уже использован")
            return
        if d["type"] == "gen":
            paid_generations[user_id] = paid_generations.get(user_id, 0) + d["amount"]
            _save_gen()
        elif d["type"] == "course":
            from course import activate_by_username
            activate_by_username(str(user_id))
            user_mode[user_id] = "course"
        d["used_by"].append(user_id)
        _save_promo(promo)
        await message.answer("✅ Активирован!")
        return
    await message.answer("🎫 /promo КОД")

# ===== ПРОМОКОДЫ - МЕНЮ =====
@dp.callback_query(F.data == "promo_menu_create")
async def promo_menu_create(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "promo_create_name"
    await callback.message.answer(
        "➕ <b>Создание промокода</b>\n\n"
        "Введи название (латиницей, например: SALE, WELCOME, INSTA10):\n\n"
        "Примеры:\n"
        "• <code>START</code> — 5 генераций\n"
        "• <code>VIP</code> — курс\n"
        "• <code>SALE30</code> — 10 генераций",
        parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "promo_menu_list")
async def promo_menu_list(callback: CallbackQuery):
    promo = _load_promo()
    if not promo:
        await callback.message.answer("📭 Нет промокодов")
    else:
        text = "🎫 <b>Промокоды:</b>\n\n"
        for c, d in promo.items():
            ptype = "🎓 Курс" if d["type"] == "course" else f"⚡ {d['amount']} ген."
            used = len(d.get("used_by", []))
            text += f"• <code>{c}</code> — {ptype} (исп: {used})\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "promo_menu_delete")
async def promo_menu_delete(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "promo_delete"
    await callback.message.answer("🗑 Введи название промокода для удаления:")
    await callback.answer()

@dp.callback_query(F.data == "promo_menu_reset")
async def promo_menu_reset(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "promo_reset"
    await callback.message.answer("🔄 Введи название промокода для сброса:")
    await callback.answer()

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
    gen_retry_count[user_id] = 0

    # Обработка custom prompt
    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "free"
        return

    if mode == "change_format":
        await message.answer("Выбери формат:",
            reply_markup=format_keyboard("paid" if paid_generations.get(user_id, 0) > 0 else "free"))
        return

    if mode == "style_photo":
        await message.answer(
            "🎨 <b>Выбери стиль:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Ч/Б", callback_data=f"gen_style_bw_free_{user_id}"),
                 InlineKeyboardButton(text="🌅 Закат", callback_data=f"gen_style_golden_free_{user_id}")],
                [InlineKeyboardButton(text="🎞️ Плёнка", callback_data=f"gen_style_film_free_{user_id}"),
                 InlineKeyboardButton(text="💡 Воздушный", callback_data=f"gen_style_highkey_free_{user_id}")],
                [InlineKeyboardButton(text="🌙 Драматичный", callback_data=f"gen_style_lowkey_free_{user_id}"),
                 InlineKeyboardButton(text="🌸 Пастель", callback_data=f"gen_style_pastel_free_{user_id}")],
                [InlineKeyboardButton(text="🌈 Ретро 80-х", callback_data=f"gen_style_retro_free_{user_id}"),
                 InlineKeyboardButton(text="🎬 Кино", callback_data=f"gen_style_cinema_free_{user_id}")],
                [InlineKeyboardButton(text="🖼️ Картина", callback_data=f"gen_style_painting_free_{user_id}"),
                 InlineKeyboardButton(text="💥 Комикс", callback_data=f"gen_style_comics_free_{user_id}")],
                [InlineKeyboardButton(text="🎌 Аниме", callback_data=f"gen_style_anime_free_{user_id}"),
                 InlineKeyboardButton(text="🎨 Акварель", callback_data=f"gen_style_aquarel_free_{user_id}")],
                [InlineKeyboardButton(text="🔥 Киберпанк", callback_data=f"gen_style_cyberpunk_free_{user_id}"),
                 InlineKeyboardButton(text="🖤 Нуар", callback_data=f"gen_style_noir_free_{user_id}")],
            ]))
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
            await message.answer("✅ Все 5 фото получены! Разберу в течение 24 часов и напишу тебе лично. Если не смогу найти — напиши мне @sevosphoto")
            _send_telegram_message(-1004468971541, f"🔔 Заказ готов!\n<a href='tg://user?id={user_id}'>👤 Пользователь</a>\nФото: {photo_count} шт")
        else:
            await message.answer(
                f"📸 Фото получено ({photo_count} из 5). Можешь прислать ещё или нажать «Готово», если это всё.",
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

        # Приглашение на курс после каждых 5 анализов
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
    
    # Обработка custom prompt
    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_wish[user_id] = message.text
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "free"
        return

    text = message.text

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

    # Обработка создания промокода
    if mode == "promo_create_name":
        user_mode[user_id] = "promo_create_value"
        gen_wish[user_id] = message.text.upper()
        await message.answer(f"Название: <b>{message.text.upper()}</b>\n\nТеперь введи количество генераций (например: 5)\nИли напиши <b>course</b> для доступа к курсу:", parse_mode="HTML")
        return

    if mode == "promo_create_value":
        code = gen_wish.get(user_id, "CODE").upper()
        if message.text.lower() == "course":
            ptype, amount = "course", 0
            type_text = "🎓 Курс"
        else:
            try:
                amount = int(message.text)
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
        code = message.text.upper()
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
        code = message.text.upper()
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
        await message.answer("Присылай фото — я проанализирую композицию! 📷")
        return
    
    if text == "✨ Улучшить":
        if user_id in last_photo:
            await message.answer("Выбери формат:", reply_markup=format_keyboard("free" if free_generations.get(user_id, 0) < 5 else "paid"))
        else:
            await message.answer("Сначала пришли фото для анализа!")
        return
    
    if text == "🎨 Стилизация":
        await message.answer(
            "🎨 Пришли фото для стилизации.\n\n"
            "Доступные стили:\n"
            "• 📸 Ч/Б — классика\n"
            "• 🌅 Закат — тёплый вечерний свет\n"
            "• 🎞️ Плёнка — винтажный вид\n"
            "• 💡 Воздушный — светлый и лёгкий\n"
            "• 🌙 Драматичный — контрастный\n"
            "• 🌸 Пастель — мягкие тона\n"
            "• 🌈 Ретро 80-х — VHS-эффект\n"
            "• 🎬 Кино — как кадр из фильма\n"
            "• 🖼️ Картина — живопись\n"
            "• 💥 Комикс — графический роман\n"
            "• 🎌 Аниме — японская анимация\n"
            "• 🎨 Акварель — мягкие разводы\n"
            "• 🔥 Киберпанк — неон и футуризм\n"
            "• 🖤 Нуар — чёрно-белый детектив",
            parse_mode="HTML"
        )
        user_mode[user_id] = "style_photo"
        return
    
    if text == "✂️ Редактор":
        await message.answer(
            "✂️ <b>Редактор</b>\n\n"
            "Загрузи фото и работай без анализа: меняй формат, улучшай, ретушируй, стилизуй.\n"
            "Все инструменты после выбора формата.\n"
            "1 генерация.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="new_photo")]]))
        user_mode[user_id] = "change_format"
        return
    
    if text == "🏠 Главное меню":
        PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
        gen_left = 5 - free_generations.get(user_id, 0) + paid_generations.get(user_id, 0)
        await message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
            caption=(
                "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
                "📸 <b>Бесплатный анализ:</b> пришли фото.\n\n"
                "✂️ <b>Редактор:</b> меняй формат, улучшай, ретушируй, стилизуй — все инструменты в одном месте.\n\n"
                "🎓 <b>Мини-курс (10 дней):</b> первый день бесплатно.\n\n"
                f"💎 Осталось генераций: {gen_left}"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
                [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
                [InlineKeyboardButton(text="💎 Мои генерации", callback_data="my_balance")],
                [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
                [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
                [InlineKeyboardButton(text="💰 Цены и поддержка", callback_data="donate_menu")],
                [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
            ]))
        return
        
    if text == "🎓 Мини-курс":
        await handle_course_status_logic(user_id, message.chat.id)
        return
    
    if text == "🎯 Авторский разбор":
        await message.answer("🎯 <b>Авторский разбор</b>\n\nЯ лично разберу твои фото.\n📷 До 5 фото\n💰 500 ₽", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]]))
        return
    
    if text == "📊 Статистика":
        stats_text = get_stats(user_id)
        await message.answer(stats_text, parse_mode="HTML")
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
        payments = 0
        try:
            pending = _load_pending_payments()
            payments = sum(1 for i in pending.values() if today in i.get("created",""))
        except:
            pass
        try:
            await bot.send_message(-1004468971541, f"📊 <b>{today}</b>\n👤 Новых: {new_users}\n📸 Анализов: {analyses}\n💰 Платежей: {payments}", parse_mode="HTML")
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
