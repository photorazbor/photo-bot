"""
Точка входа: Telegram-бот на aiogram 3 + заглушка для Render
"""
import asyncio
import logging
from threading import Thread
from flask import Flask, request
import os
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
from image_utils import download_and_resize, image_to_bytes, draw_hints, align_interior, check_and_crop_doc_photo
from stats import add_analysis, get_stats, add_history as stats_add_history, _load_stats as load_stats_data
from course import get_status, add_photo, check_day, has_access, get_day_photos, _load_users, activate_free_trial
from xmas import (
    register_xmas_handlers,
    handle_xmas_photo,
    handle_xmas_custom_text,
    is_user_in_xmas_flow,
    reset_xmas_state,
    xmas_awaiting_photo,
    XMAS_INTRO,
    locations_keyboard as xmas_locations_keyboard,
)

from reference import (
    register_reference_handlers,
    handle_reference_photo,
    reset_ref_state,
    is_user_in_ref_flow,
)

from daily import (
    register_daily_handlers,
    reset_daily_state,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

MAIN_LOOP = None
flask_app = Flask(__name__)

from holidays import (
    register_holidays_handlers,
    handle_holiday_photo,
    handle_holiday_custom_text,
    reset_holiday_state,
    is_user_in_holiday_flow,
    holiday_awaiting_photo,
)

from wedding import (
    register_wedding_handlers,
    handle_wedding_photo,
    handle_wedding_custom_text,
    reset_wedding_state,
    is_user_in_wedding_flow,
    wedding_awaiting_photo,
    wedding_awaiting_names,
    wedding_awaiting_date,
)

from prompt_image import (
    register_prompt_handlers,
    handle_prompt_text,
    handle_prompt_photo,
    reset_prompt_state,
    is_user_in_prompt_flow,
    prompt_awaiting_photo,
    prompt_awaiting_text,
)

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ===== КОНСТАНТЫ =====
FREE_GENERATIONS = 3
FREE_ANALYSIS_PER_DAY = 5

USER_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎉 Праздники"), KeyboardButton(text="🔮 Карта дня")],
        [KeyboardButton(text="📸 Разобрать фото"), KeyboardButton(text="🛠 Инструменты")],
        [KeyboardButton(text="🎓 Мини-курс"), KeyboardButton(text="🎯 Авторский разбор")],
        [KeyboardButton(text="💎 Баланс"), KeyboardButton(text="💛 Поддержать проект")],
        [KeyboardButton(text="👤 Об авторе"), KeyboardButton(text="🏠 Главное меню")],
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
studio_angle_choice = {}
studio_bg_choice = {}
studio_outfit_choice = {}
studio_hair_choice = {}
doc_attempts = {}
DOC_ATTEMPTS_FILE = "doc_attempts.json"
GEN_FILE = "generations.json"
doc_type_last = {}
last_photo = {}
original_photo = {}
gen_wish = {}
gen_format = {}
gen_retry_count = {}
gen_used_count = {}
gen_fail_count = {}
gen_fail_time = {}
flat_lay_active = {}
flat_lay_style = {}
style_active = {}   # True, если генерация идёт из «Стилизации»
editor_mode = {}    # True, если пользователь пришёл из Редактора
last_prompt = {}
last_format = {}
interior_active = {}
interior_format = {}
interior_light = {}
change_format_warnings = {}
test_mode = False
TEST_MODE_FILE = "test_mode.json"

# ===== АНАЛИЗ: СЧЁТЧИК ДНЕВНОЙ =====
analysis_today = {}
ANALYSIS_FILE = "analysis_count.json"

# ===== АНАЛИЗ: ПЛАТНЫЕ ПАКЕТЫ =====
paid_analyses = {}   # {user_id: int}
PAID_ANALYSES_FILE = "paid_analyses.json"


def _load_analysis_count():
    global analysis_today
    if os.path.exists(ANALYSIS_FILE):
        try:
            with open(ANALYSIS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                analysis_today = {int(k): v for k, v in data.items()}
        except Exception:
            analysis_today = {}

def _load_paid_analyses():
    global paid_analyses
    if os.path.exists(PAID_ANALYSES_FILE):
        try:
            with open(PAID_ANALYSES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                paid_analyses = {int(k): v for k, v in data.items()}
        except Exception:
            paid_analyses = {}


def _save_paid_analyses():
    with open(PAID_ANALYSES_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in paid_analyses.items()}, f, ensure_ascii=False, indent=2)


def _save_analysis_count():
    with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in analysis_today.items()}, f, ensure_ascii=False, indent=2)


def _analysis_check_and_get(user_id: int):
    """Возвращает (можно_ли_анализировать, сколько_осталось_всего)."""
    if user_id == 456504792 and test_mode:
        return True, 999
    today = datetime.now().strftime("%Y-%m-%d")
    rec = analysis_today.get(user_id)
    if not rec or rec.get("date") != today:
        analysis_today[user_id] = {"date": today, "count": 0}
        _save_analysis_count()
        free_left = FREE_ANALYSIS_PER_DAY
    else:
        count = rec.get("count", 0)
        free_left = max(0, FREE_ANALYSIS_PER_DAY - count)
    paid_left = paid_analyses.get(user_id, 0)
    total_left = free_left + paid_left
    return total_left > 0, total_left


def _analysis_get_free_left(user_id: int) -> int:
    """Сколько бесплатных анализов осталось сегодня."""
    if user_id == 456504792 and test_mode:
        return 999
    today = datetime.now().strftime("%Y-%m-%d")
    rec = analysis_today.get(user_id)
    if not rec or rec.get("date") != today:
        return FREE_ANALYSIS_PER_DAY
    return max(0, FREE_ANALYSIS_PER_DAY - rec.get("count", 0))


def _analysis_increment(user_id: int):
    """Списывает 1 анализ: сначала бесплатные, потом платные."""
    if user_id == 456504792 and test_mode:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    rec = analysis_today.get(user_id)
    if not rec or rec.get("date") != today:
        analysis_today[user_id] = {"date": today, "count": 1}
        _save_analysis_count()
        return
    count = rec.get("count", 0)
    if count < FREE_ANALYSIS_PER_DAY:
        analysis_today[user_id]["count"] = count + 1
        _save_analysis_count()
        return
    # Бесплатные кончились — списываем платные
    if paid_analyses.get(user_id, 0) > 0:
        paid_analyses[user_id] = paid_analyses[user_id] - 1
        _save_paid_analyses()


def _load_test_mode():
    global test_mode
    if os.path.exists(TEST_MODE_FILE):
        try:
            with open(TEST_MODE_FILE, "r") as f:
                data = json.load(f)
                test_mode = data.get("enabled", False)
        except Exception:
            test_mode = False


def _save_test_mode():
    with open(TEST_MODE_FILE, "w") as f:
        json.dump({"enabled": test_mode}, f)


_load_test_mode()

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


def _reset_all_flows(user_id: int):
    """Сбрасывает все «ожидающие» состояния пользователя."""
    try:
        from xmas import reset_xmas_state
        reset_xmas_state(user_id)
    except Exception:
        pass
    try:
        from holidays import reset_holiday_state
        reset_holiday_state(user_id)
    except Exception:
        pass
    try:
        from wedding import reset_wedding_state
        reset_wedding_state(user_id)
    except Exception:
        pass
    try:
        from reference import reset_ref_state
        reset_ref_state(user_id)
    except Exception:
        pass
    try:
        from daily import reset_daily_state
        reset_daily_state(user_id)
    except Exception:
        pass
    try:
        from prompt_image import reset_prompt_state
        reset_prompt_state(user_id)
    except Exception:
        pass


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
    "3x4": "354x472",
    "passport": "413x531",
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

PORTRAIT_FORMATS = [
    ("original", "📐 Исходный формат"),
    ("1_1", "📱 1:1 (квадрат)"),
    ("3_4", "📱 3:4 (вертикаль)"),
    ("4_3", "🖼️ 4:3 (горизонт)"),
    ("4_5", "📱 4:5 (Instagram)"),
    ("9_16", "📱 9:16 (сториз)"),
]

DOC_FORMATS = {
    "passport": ("35×45 мм (паспорт РФ, универсальный)", 413, 531),
    "3x4": ("30×40 мм (3×4, удостоверения)", 354, 472),
}


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
    if fmt in ("passport", "3x4"):
        return SIZE_MAP[fmt]
    key = fmt.replace("_", ":")
    return SIZE_MAP.get(key, "1024x1024")


def format_keyboard(gen_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"gen_{fmt}_{gen_type}")]
        for fmt, name in FORMATS
    ])


def portrait_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"pformat_{fmt}")]
        for fmt, name in PORTRAIT_FORMATS
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
_load_analysis_count()
_load_paid_analyses()


def get_balance(user_id: int) -> int:
    if user_id == 456504792 and test_mode:
        return 999
    free_left = max(0, FREE_GENERATIONS - free_generations.get(user_id, 0))
    paid_left = paid_generations.get(user_id, 0)
    return free_left + paid_left


def spend_generation(user_id: int) -> bool:
    if user_id == 456504792 and test_mode:
        return True
    free_used = free_generations.get(user_id, 0)
    if free_used < FREE_GENERATIONS:
        free_generations[user_id] = free_used + 1
        _save_gen()
        return True
    if paid_generations.get(user_id, 0) > 0:
        paid_generations[user_id] = paid_generations[user_id] - 1
        _save_gen()
        return True
    return False


def _load_doc_attempts():
    global doc_attempts
    if os.path.exists(DOC_ATTEMPTS_FILE):
        with open(DOC_ATTEMPTS_FILE, "r") as f:
            data = json.load(f)
            doc_attempts = {int(k): v for k, v in data.items()}


def _save_doc_attempts():
    with open(DOC_ATTEMPTS_FILE, "w") as f:
        json.dump({str(k): v for k, v in doc_attempts.items()}, f, ensure_ascii=False, indent=2)


_load_doc_attempts()


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
        "ПОЛНОСТЬЮ замени исходный фон — НЕ сохраняй стол, на котором снято фото. "
        "Создай УЮТНЫЙ Flat Lay как из Pinterest. "
        "Фон — тёплый деревянный стол ИЛИ фактурная светлая поверхность: лён, керамика, светлый камень. "
        "С ЕСТЕСТВЕННОЙ, умеренной текстурой. "
        "Добавь ЛЁГКИЙ КОНТРАСТ: мягкие тени от предметов, естественные световые переходы. "
        "Избегай крайностей: не слишком тёмный, не слишком светлый. "
        "Всё должно выглядеть натурально и естественно. "
        "РАСПОЗНАЙ, ЧТО ЗА ПРЕДМЕТЫ, и подбери декор ИМЕННО под эту тематику. "
        "ЕСЛИ это еда — красиво разложи её: аппетитно, ровно, не скомканно. "
        "Сушёные фрукты остаются сушёными, но выглядят эстетично. "
        "Можно добавить свежие фрукты рядом для контраста. "
        "Еда должна выглядеть как в фуд-фотографии. "
        "НЕ добавляй новые продукты, которых не было на фото. "
        "Если сухофруктов нет — не добавляй курагу, миндаль, орехи. "
        "Если это обувь — добавь шнурки, коробку, ткань. "
        "Если спорт — гантели, полотенце, бутылку воды. "
        "Если косметика — кисти, зеркало, цветы. "
        "Если книги — очки, закладку. "
        "ЕСЛИ в кадре есть руки — сохрани их как на фото. "
        "НЕ дорисовывай кольца, часы, браслеты, если их не было на фото. "
        "Если украшения есть — сохрани их. "
        "РАССТАВЬ предметы красиво и гармонично — измени расположение. "
        "Мягкий естественный свет с лёгкими тенями для объёма. "
        "Сохрани все предметы с фото. "
        "СТРОГИЕ ПРАВИЛА ПО КОФЕ И НАПИТКАМ: "
        "Добавляй кофе, чай или другие напитки ТОЛЬКО если они УЖЕ ЕСТЬ на исходном фото. "
        "Если на фото спортинвентарь, техника, книги, одежда, обувь, инструменты — НЕ добавляй никаких напитков. "
        "Если чашка кофе есть на фото — сделай её аккуратной. "
        "Определи тип напитка по объёму и форме чашки: "
        "маленькая чашка (100-150 мл) — эспрессо: тёмный крепкий, тонкая кремовая пенка; "
        "средняя чашка (200-250 мл) — американо: тёмный прозрачный, без пенки; "
        "большая кружка (300+ мл) — капучино: светлый с плотной молочной пенкой; "
        "широкая чашка с ручкой — латте: молочная пенка с латте-артом (сердце, розетта, лист). "
        "НЕ оставляй следы от выпитого кофе, осадок, тёмные разводы по краям. "
        "Замени на аккуратный свежий напиток, как будто только что налили. "
        "Если кофе на фото НЕТ — НЕ добавляй его. "
        "СТРОГИЕ ПРАВИЛА ПО КАМНЯМ И ДЕКОРУ: "
        "НЕ добавляй камни, булыжники, гальку, если их НЕ было на исходном фото. "
        "Декор подбирай ИСКЛЮЧИТЕЛЬНО под тематику предметов — без универсальных камней и сухоцветов."
    ),
    "minimal": (
        "ПОЛНОСТЬЮ замени исходный фон — НЕ сохраняй стол, на котором снято фото. "
        "Создай МИНИМАЛИСТИЧНЫЙ Flat Lay как из Pinterest. "
        "Фон — чистый белый ИЛИ светло-серый, однотонный. "
        "РАСПОЗНАЙ, ЧТО ЗА ПРЕДМЕТЫ, и подбери МИНИМУМ декора под тематику. "
        "ЕСЛИ это еда — красиво разложи её: аппетитно, ровно. "
        "Сушёные фрукты остаются сушёными, но выглядят эстетично. "
        "НЕ добавляй новые продукты, которых не было на фото. "
        "Если сухофруктов нет — не добавляй курагу, миндаль, орехи. "
        "НЕ добавляй чай или кофе, если это не еда. "
        "ЕСЛИ в кадре есть руки — сохрани их как на фото. "
        "НЕ дорисовывай кольца, часы, браслеты, если их не было на фото. "
        "РАССТАВЬ предметы идеально — измени расположение, создай геометрию. "
        "Много пустого пространства. "
        "Мягкий рассеянный свет. "
        "Сохрани все предметы. "
        "СТРОГИЕ ПРАВИЛА ПО КОФЕ И НАПИТКАМ: "
        "Добавляй кофе, чай или другие напитки ТОЛЬКО если они УЖЕ ЕСТЬ на исходном фото. "
        "Если на фото спортинвентарь, техника, книги, одежда, обувь, инструменты — НЕ добавляй никаких напитков. "
        "Если чашка кофе есть на фото — сделай её аккуратной. "
        "Определи тип напитка по объёму и форме чашки: "
        "маленькая чашка — эспрессо: тёмный крепкий, тонкая кремовая пенка; "
        "средняя — американо: тёмный прозрачный, без пенки; "
        "большая кружка — капучино: светлый с молочной пенкой; "
        "широкая чашка с ручкой — латте: молочная пенка с латте-артом. "
        "НЕ оставляй следы от выпитого кофе, осадок, разводы. "
        "Замени на аккуратный свежий напиток. "
        "Если кофе на фото НЕТ — НЕ добавляй его. "
        "СТРОГИЕ ПРАВИЛА ПО КАМНЯМ: "
        "НЕ добавляй камни, булыжники, гальку, если их НЕ было на фото. "
        "Декор — только по теме."
    ),
    "nature": (
        "ПОЛНОСТЬЮ замени исходный фон — НЕ сохраняй стол, на котором снято фото. "
        "Создай ПРИРОДНЫЙ Flat Lay как из Pinterest. "
        "Фон должен быть НАТУРАЛЬНЫМ и ГАРМОНИЧНЫМ — подбери то, что лучше всего подходит к предметам. "
        "Это может быть: светлое дерево, камень, мрамор, лён, керамика. "
        "Главное — фон должен выглядеть ЦЕЛЬНЫМ, ЕСТЕСТВЕННЫМ и КРАСИВЫМ. "
        "НЕ делай лоскутный фон из кусков разных материалов. "
        "РАСПОЗНАЙ, ЧТО ЗА ПРЕДМЕТЫ, и создай ГАРМОНИЧНУЮ композицию. "
        "ЕСЛИ это еда — красиво разложи её: аппетитно, ровно, не скомканно. "
        "Сушёные фрукты переразложи аккуратно, чтобы выглядели эстетично. "
        "Добавь уместные элементы: свежие фрукты, зелень, цветы, листья. "
        "НЕ добавляй орехи, если их не было на фото. "
        "НЕ добавляй сухую траву или мусор. "
        "ЕСЛИ в кадре есть руки — сохрани их как на фото. "
        "НЕ дорисовывай кольца, часы, браслеты, если их не было на фото. "
        "РАССТАВЬ предметы гармонично и живописно — измени расположение. "
        "Мягкий дневной свет с лёгкими тенями. "
        "Сохрани все предметы. "
        "СТРОГИЕ ПРАВИЛА ПО КОФЕ И НАПИТКАМ: "
        "Добавляй кофе, чай или другие напитки ТОЛЬКО если они УЖЕ ЕСТЬ на исходном фото. "
        "Если на фото спортинвентарь, техника, книги, одежда, инструменты — НЕ добавляй напитков. "
        "Если чашка кофе есть — определи тип: "
        "маленькая — эспрессо (тёмный, тонкая пенка); "
        "средняя — американо (тёмный, прозрачный); "
        "большая — капучино (молочная пенка); "
        "широкая с ручкой — латте (пенка с латте-артом). "
        "НЕ оставляй следы от выпитого кофе и осадок. "
        "Замени на свежий аккуратный напиток. "
        "Если кофе НЕТ — НЕ добавляй. "
        "СТРОГИЕ ПРАВИЛА ПО КАМНЯМ: "
        "НЕ добавляй камни, булыжники, гальку, если их НЕ было на фото. "
        "Природный декор — только уместный: листья, цветы, фрукты, зелень."
    ),
    "dark": (
        "ПОЛНОСТЬЮ замени исходный фон — НЕ сохраняй стол, на котором снято фото. "
        "Создай Flat Lay в стиле НИЗКИЙ КЛЮЧ, как из Pinterest. "
        "Фон — тёмный: графит, тёмный бетон, тёмный камень, тёмное дерево, шифер. "
        "Фактура может быть матовой, шероховатой, с лёгкими прожилками. "
        "НО это не значит, что всё должно быть чёрным. "
        "Предметы и декор — ПРИГЛУШЁННЫХ НАТУРАЛЬНЫХ тонов: "
        "бежевый, серый, оливковый, тёмно-зелёный, бордовый, тёмно-синий, охра, тёмное золото. "
        "Избегай кислотных и неоновых цветов. "
        "Всё должно быть в тёмной гамме, но с естественными цветовыми переходами. "
        "НЕ делай весь декор чёрным — добавь приглушённые СВЕТЛЫЕ акценты: светлый камень, сухоцветы, светлое дерево. "
        "Контраст — мягкий, естественный, не резкий. "
        "ЕСЛИ это еда — красиво разложи её: аппетитно, ровно. "
        "Сушёные фрукты остаются сушёными, но выглядят эстетично. "
        "НЕ добавляй новые продукты, которых не было на фото. "
        "Добавь драматичный боковой свет, чтобы предметы выделялись. "
        "РАСПОЗНАЙ, ЧТО ЗА ПРЕДМЕТЫ, и подбери уместный декор. "
        "НЕ добавляй напитки, если это не еда. "
        "ЕСЛИ в кадре есть руки — сохрани их как на фото. "
        "НЕ дорисовывай кольца, часы, браслеты, если их не было на фото. "
        "РАССТАВЬ предметы стильно — измени расположение. "
        "Глубокие тени, блики, объём. "
        "Сохрани все предметы. "
        "СТРОГИЕ ПРАВИЛА ПО КОФЕ И НАПИТКАМ: "
        "Добавляй кофе, чай ТОЛЬКО если они УЖЕ ЕСТЬ на исходном фото. "
        "Если на фото спортинвентарь, техника, книги, обувь, инструменты — НЕ добавляй напитков. "
        "Если чашка кофе есть — определи тип: "
        "маленькая — эспрессо (тёмный, тонкая кремовая пенка); "
        "средняя — американо (тёмный прозрачный); "
        "большая кружка — капучино (плотная молочная пенка); "
        "широкая с ручкой — латте (пенка с латте-артом). "
        "НЕ оставляй следы от выпитого, осадок, тёмные разводы. "
        "Замени на свежий аккуратный напиток. "
        "Если кофе НЕТ — НЕ добавляй. "
        "СТРОГИЕ ПРАВИЛА ПО КАМНЯМ: "
        "НЕ добавляй камни и гальку, если их НЕ было на фото. "
        "Декор — только по теме."
    ),
    "pastel": (
        "ПОЛНОСТЬЮ замени исходный фон — НЕ сохраняй стол, на котором снято фото. "
        "Создай НЕЖНЫЙ ПАСТЕЛЬНЫЙ Flat Lay как из Pinterest. "
        "Фон — пастельный однотонный ИЛИ пастельный мрамор ИЛИ пастельная ткань. "
        "РАСПОЗНАЙ, ЧТО ЗА ПРЕДМЕТЫ, и добавь нежный декор под тематику. "
        "ЕСЛИ это еда — красиво разложи её: аппетитно, ровно, не скомканно. "
        "Сушёные фрукты остаются сушёными, но выглядят эстетично. "
        "Можно добавить свежие фрукты или цветы для контраста. "
        "НЕ добавляй еду или напитки, если это не еда. "
        "НЕ добавляй новые продукты, которых не было на фото. "
        "Если сухофруктов нет — не добавляй. "
        "ЕСЛИ в кадре есть руки — сохрани их как на фото. "
        "НЕ дорисовывай кольца, часы, браслеты, если их не было на фото. "
        "РАССТАВЬ предметы красиво — измени расположение. "
        "Мягкий воздушный свет. "
        "Сохрани все предметы. "
        "СТРОГИЕ ПРАВИЛА ПО КОФЕ И НАПИТКАМ: "
        "Добавляй кофе, чай ТОЛЬКО если они УЖЕ ЕСТЬ на фото. "
        "Если на фото спортинвентарь, техника, книги, обувь — НЕ добавляй напитков. "
        "Если чашка кофе есть — определи тип: "
        "маленькая — эспрессо (тёмный, тонкая пенка); "
        "средняя — американо (тёмный прозрачный); "
        "большая — капучино (светлый с молочной пенкой); "
        "широкая с ручкой — латте (пенка с латте-артом). "
        "НЕ оставляй следы от выпитого, осадок, разводы. "
        "Замени на свежий аккуратный напиток. "
        "Если кофе НЕТ — НЕ добавляй. "
        "СТРОГИЕ ПРАВИЛА ПО КАМНЯМ: "
        "НЕ добавляй камни и гальку, если их НЕ было на фото. "
        "Декор — только по теме."
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

                    if "Пакет 30 анализов" in purp:
                        paid_analyses[uid] = paid_analyses.get(uid, 0) + 30
                        _save_paid_analyses()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! +30 анализов начислены.\n\nПакет не сгорает — тратится, когда кончится бесплатный лимит."),
                            MAIN_LOOP
                        )
                    elif "Пакет 100 анализов" in purp:
                        paid_analyses[uid] = paid_analyses.get(uid, 0) + 100
                        _save_paid_analyses()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! +100 анализов начислены."),
                            MAIN_LOOP
                        )
                    elif "Пакет 300 анализов" in purp:
                        paid_analyses[uid] = paid_analyses.get(uid, 0) + 300
                        _save_paid_analyses()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! +300 анализов начислены."),
                            MAIN_LOOP
                        )
                    elif "Пакет 5 генераций" in purp:
                        paid_generations[uid] = paid_generations.get(uid, 0) + 5
                        _save_gen()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! 5 генераций начислены.\n\nЗаходи в /start и продолжай."),
                            MAIN_LOOP
                        )
                    elif "Пакет 10 генераций" in purp:
                        paid_generations[uid] = paid_generations.get(uid, 0) + 10
                        _save_gen()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! 10 генераций начислены."),
                            MAIN_LOOP
                        )
                    elif "Пакет 30 генераций" in purp:
                        paid_generations[uid] = paid_generations.get(uid, 0) + 30
                        _save_gen()
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! 30 генераций начислены."),
                            MAIN_LOOP
                        )
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
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! Присылай до 5 фото по одному. Нажми «Готово» когда закончишь."),
                            MAIN_LOOP
                        )
                        _send_telegram_message(-1004468971541, f"🔔 Новый заказ на авторский разбор!\nПользователь: {uid}")
                    elif "мини-курс" in purp or "курс" in purp:
                        from course import activate_by_username
                        activate_by_username(str(uid))
                        user_mode[uid] = "course"
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(uid, "✅ Оплата получена! Мини-курс активирован. Напиши /course"),
                            MAIN_LOOP
                        )
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


def buy_generations_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 5 генераций — 59 ₽", callback_data="buy_5_gen")],
        [InlineKeyboardButton(text="⚡ 10 генераций — 99 ₽", callback_data="buy_10_gen")],
        [InlineKeyboardButton(text="⚡ 30 генераций — 249 ₽", callback_data="buy_30_gen")],
    ])


def buy_analyses_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 +30 анализов — 49 ₽", callback_data="buy_30_analysis")],
        [InlineKeyboardButton(text="🔍 +100 анализов — 129 ₽", callback_data="buy_100_analysis")],
        [InlineKeyboardButton(text="🔍 +300 анализов — 299 ₽", callback_data="buy_300_analysis")],
    ])


def balance_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 +30 анализов — 49 ₽", callback_data="buy_30_analysis")],
        [InlineKeyboardButton(text="🔍 +100 анализов — 129 ₽", callback_data="buy_100_analysis")],
        [InlineKeyboardButton(text="🔍 +300 анализов — 299 ₽", callback_data="buy_300_analysis")],
        [InlineKeyboardButton(text="⚡ 5 генераций — 59 ₽", callback_data="buy_5_gen")],
        [InlineKeyboardButton(text="⚡ 10 генераций — 99 ₽", callback_data="buy_10_gen")],
        [InlineKeyboardButton(text="⚡ 30 генераций — 249 ₽", callback_data="buy_30_gen")],
    ])


def get_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    balance = get_balance(user_id)
    if balance > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото ({balance} ген.)", callback_data="gen_start")])
    else:
        buttons.append([InlineKeyboardButton(text="⚡ Купить генерации", callback_data="show_buy_menu")])
    buttons.append([InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")])
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


async def do_generation(user_id: int, chat_id: int, gen_type: str, check_diff: bool = True,
                        use_original: bool = False, mode: str = "normal"):
    if user_id not in last_photo:
        await bot.send_message(chat_id, "Сначала пришли фото для анализа!")
        return

    # Проверка и списание баланса
    if mode != "retry":
        if not (user_id == 456504792 and test_mode):
            if get_balance(user_id) <= 0:
                await bot.send_message(
                    chat_id,
                    "💎 Генерации закончились.\n\nПополни баланс — и продолжай:",
                    reply_markup=buy_generations_keyboard()
                )
                return
        if not spend_generation(user_id):
            await bot.send_message(
                chat_id,
                "💎 Генерации закончились.\n\nПополни баланс — и продолжай:",
                reply_markup=buy_generations_keyboard()
            )
            return

    fmt = gen_format.get(user_id, "1_1")
    wish = gen_wish.get(user_id, "")
    is_flat_lay = flat_lay_active.get(user_id, False)

    if mode == "retry" and user_id in original_photo:
        image_bytes = original_photo[user_id]
    elif is_flat_lay:
        image_bytes = last_photo[user_id]
    elif use_original and user_id in original_photo:
        image_bytes = original_photo[user_id]
    else:
        image_bytes = last_photo[user_id]

    if mode == "retry":
        await bot.send_message(chat_id, "🔄 Генерирую другой вариант...")
    elif mode == "boost":
        await bot.send_message(chat_id, "⚡ Усиливаю обработку...")
    else:
        await bot.send_message(chat_id, "🎨 Генерирую изображение... Это занимает около минуты.")

    try:
        img_size = get_size_for_format(fmt, image_bytes)
        analysis = last_analysis.get(user_id, {})
        error_type = analysis.get("error_type", "")
        what_is_wrong = analysis.get("what_is_wrong", "")

        if is_flat_lay:
            saved_style = flat_lay_style.get(user_id, "")
            if saved_style and saved_style in FLAT_LAY_PROMPTS:
                prompt = f"{FLAT_LAY_PROMPTS[saved_style]} Размер: {img_size}. "
            elif wish and wish.lower() != "ок":
                prompt = f"{wish} Размер: {img_size}. "
            else:
                prompt = f"Создай стильный Flat Lay. Размер: {img_size}. "
            if mode == "retry":
                prompt += " Сделай ДРУГОЙ вариант. Не повторяй предыдущий результат. "
            elif mode == "boost":
                prompt += " Усиль обработку ЗНАЧИТЕЛЬНО. Изменения должны быть очень заметными. "

        elif wish and wish.lower() != "ок":
            prompt = (
                f"{wish} "
                f"ВАЖНО: сохрани всех людей, их лица, одежду, причёски, аксессуары и объекты с исходного фото. "
                f"НЕ добавляй новых людей, животных, предметов, которых не было на исходном фото. "
                f"НЕ убирай существующие объекты. "
                f"Сохрани общий смысл, сюжет и атмосферу кадра. "
                f"Размер: {img_size}. "
            )
            if mode == "retry":
                prompt += " Сделай ДРУГОЙ вариант. Не повторяй предыдущий результат. "
            elif mode == "boost":
                prompt += " Усиль обработку ЗНАЧИТЕЛЬНО. Изменения должны быть очень заметными. "

        else:
            prompt = (
                f"Улучши это фото как опытный ретушёр. "
                f"Дорисуй обрезанные края — особенно конечности и низ. "
                f"Исправь неестественную позу, если нужно. "
                f"Убери только явно случайный мусор с фона. "
                f"Улучши свет и цвета. "
                f"НЕ меняй черты лица, выражение, людей — как на фото. "
                f"НЕ добавляй новые объекты. "
                f"Верхнюю одежду не меняй. "
                f"Если дорисовываешь низ — современный стиль: "
                f"брюки прямые, свободные, широкие джинсы, чиносы. "
                f"Платье прямого силуэта, миди. "
                f"Обувь по контексту: улица — обувь, дом — можно без. "
                f"Фигуру сохрани КАК НА ФОТО — живот не добавляй, "
                f"если его нет на исходном. "
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
            if what_is_wrong and what_is_wrong != "---":
                prompt += (
                    f" Найди и исправь конкретно эту ошибку: {what_is_wrong}. "
                    f"Сделай изменения заметными."
                )

        result = generate_image(image_bytes, prompt)
        if result is None:
            await bot.send_message(chat_id, "😕 Не получилось с первого раза. Пробую ещё раз...")
            result = generate_image(image_bytes, prompt)
            if result is None:
                last_fail_time = gen_fail_time.get(user_id)
                if last_fail_time and (datetime.now() - last_fail_time).total_seconds() > 900:
                    gen_fail_count[user_id] = 0
                gen_fail_count[user_id] = gen_fail_count.get(user_id, 0) + 1
                gen_fail_time[user_id] = datetime.now()
                if gen_fail_count.get(user_id, 0) >= 3:
                    await bot.send_message(
                        chat_id,
                        "😔 Сервис временно недоступен.\n\n"
                        "✅ Генерация НЕ списана.\n"
                        "🔄 Попробуйте через 10-15 минут."
                    )
                else:
                    await bot.send_message(
                        chat_id,
                        "😔 Не удалось сгенерировать.\n\n"
                        "✅ Генерация НЕ списана.\n"
                        "🔄 Нажми ту же кнопку ещё раз."
                    )
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
            mode_now = user_mode.get(user_id, "")
            if not mode_now.startswith("doc_"):
                target_size_str = get_size_for_format(fmt, image_bytes)
                try:
                    tw, th = map(int, target_size_str.split("x"))
                    if fmt != "original" and (img.width, img.height) != (tw, th):
                        target_ratio = tw / th
                        src_ratio = img.width / img.height
                        if src_ratio > target_ratio:
                            new_w = int(img.height * target_ratio)
                            left = (img.width - new_w) // 2
                            img = img.crop((left, 0, left + new_w, img.height))
                        else:
                            new_h = int(img.width / target_ratio)
                            top = (img.height - new_h) // 2
                            img = img.crop((0, top, img.width, top + new_h))
                        img = img.resize((tw, th), Image.LANCZOS)
                except Exception:
                    pass
            buf = io_module.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            result = buf.getvalue()
        except Exception:
            pass

        if user_mode.get(user_id, "").startswith("doc_"):
            result = check_and_crop_doc_photo(result, doc_type_last.get(user_id, "passport"))

        last_photo[user_id] = result
        gen_fail_count[user_id] = 0
        gen_fail_time[user_id] = None

        mode_check = user_mode.get(user_id, "")
        if mode_check.startswith("doc_"):
            doc_type = doc_type_last.get(user_id, "passport")
            format_name = DOC_FORMATS.get(doc_type, ("35×45 мм", 0, 0))[0]
        elif mode_check.startswith("studio_"):
            format_name = dict(PORTRAIT_FORMATS).get(fmt, fmt)
        else:
            format_name = dict(FORMATS).get(fmt, fmt)

        balance = get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

        await bot.send_photo(
            chat_id,
            BufferedInputFile(result, filename="generated.jpg"),
            caption=f"✨ Готово!\nФормат: {format_name}\n\n💎 Баланс: {balance_text}"
        )

        # Кнопки после генерации
        if user_mode.get(user_id, "").startswith("studio_"):
            # После перегенерации кнопку "Перегенерировать" не показываем
            if mode == "retry" or gen_retry_count.get(user_id, 0) >= 1:
                studio_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📸 Создать ещё портрет", callback_data=f"studio_next_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            else:
                studio_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data=f"studio_retry_{user_id}")],
                    [InlineKeyboardButton(text="📸 Создать ещё портрет", callback_data=f"studio_next_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            await bot.send_message(chat_id, "Что дальше?", reply_markup=studio_kb)
            return

        if user_mode.get(user_id, "").startswith("doc_"):
            # Определяем размер по типу документа
            _doc_type = doc_type_last.get(user_id, "passport")
            if _doc_type == "3x4":
                _size_text = "30×40 мм (3×4)"
            else:
                _size_text = "35×45 мм (паспорт РФ)"
            if mode == "retry" or gen_retry_count.get(user_id, 0) >= 1:
                doc_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📸 Новый документ", callback_data=f"doc_next_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            else:
                doc_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data=f"doc_retry_{user_id}")],
                    [InlineKeyboardButton(text="📸 Новый документ", callback_data=f"doc_next_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            await bot.send_message(
                chat_id,
                "📄 <b>Что дальше с фото:</b>\n\n"
                "1. Сохрани фото (нажми на картинку → «Сохранить в галерею»)\n"
                "2. Отправь в фотосалон или распечатай сам\n"
                f"3. Скажи в салоне: «Распечатайте по нормативу, размер {_size_text}»\n"
                "4. Они сами откадрируют и сделают нужное количество\n\n"
                "⚠️ Фото уже готово к печати — с запасом по краям.",
                parse_mode="HTML"
            )
            await bot.send_message(chat_id, "Что дальше?", reply_markup=doc_kb)
            return

        if style_active.get(user_id, False):
            if mode == "retry" or gen_retry_count.get(user_id, 0) >= 1:
                post_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎨 Новая стилизация", callback_data="style_photo")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            else:
                post_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Перегенерировать (бесплатно)", callback_data=f"gen_retry_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="🎨 Новая стилизация", callback_data="style_photo")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            await bot.send_message(chat_id, "Что дальше?", reply_markup=post_kb)
            return

        if is_flat_lay:
            if mode == "retry" or gen_retry_count.get(user_id, 0) >= 1:
                flat_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Доработать", callback_data=f"flat_refine_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                     InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
                    [InlineKeyboardButton(text=f"💎 Баланс: {balance_text}", callback_data="my_balance")],
                    [InlineKeyboardButton(text="📷 Новый Flat Lay", callback_data=f"flat_new_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            else:
                flat_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Доработать", callback_data=f"flat_refine_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data=f"gen_retry_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                     InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
                    [InlineKeyboardButton(text=f"💎 Баланс: {balance_text}", callback_data="my_balance")],
                    [InlineKeyboardButton(text="📷 Новый Flat Lay", callback_data=f"flat_new_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            await bot.send_message(chat_id, "Что дальше?", reply_markup=flat_kb)
        else:
            if mode == "retry" or gen_retry_count.get(user_id, 0) >= 1:
                post_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Доработать результат", callback_data=f"gen_refine_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                     InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
                    [InlineKeyboardButton(text=f"💎 Баланс: {balance_text}", callback_data="my_balance")],
                    [InlineKeyboardButton(text="📷 Новое фото", callback_data=f"new_photo_same_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            else:
                post_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Доработать результат", callback_data=f"gen_refine_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="🔄 Перегенерировать (бесплатно)", callback_data=f"gen_retry_{gen_type}_{user_id}")],
                    [InlineKeyboardButton(text="👍 Хорошо", callback_data=f"fb_good_{user_id}"),
                     InlineKeyboardButton(text="👎 Плохо", callback_data=f"fb_bad_{user_id}")],
                    [InlineKeyboardButton(text=f"💎 Баланс: {balance_text}", callback_data="my_balance")],
                    [InlineKeyboardButton(text="📷 Новое фото", callback_data=f"new_photo_same_{user_id}")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            await bot.send_message(chat_id, "Что дальше?", reply_markup=post_kb)

        last_prompt[user_id] = wish if wish else ""
        last_format[user_id] = fmt if fmt else ""

    except Exception as e:
        logger.exception("Ошибка генерации")
        gen_fail_count[user_id] = gen_fail_count.get(user_id, 0) + 1
        if gen_fail_count.get(user_id, 0) >= 3:
            await bot.send_message(
                chat_id,
                "😔 Сервис временно недоступен.\n\n"
                "✅ Генерация НЕ списана.\n"
                "🔄 Попробуйте через 10-15 минут."
            )
        else:
            await bot.send_message(
                chat_id,
                "😔 Не удалось сгенерировать.\n\n"
                "✅ Генерация НЕ списана.\n"
                "🔄 Нажми ту же кнопку ещё раз."
            )


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
    balance = get_balance(message.from_user.id)
    balance_text = "∞" if (message.from_user.id == 456504792 and test_mode) else str(balance)

    await message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
        caption=(
            "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
            "Помогаю снимать лучше, обрабатывать умнее и создавать "
            "красивые кадры. Всё — прямо в Telegram.\n\n"
            "📸 <b>Разбор фото</b>\n"
            "Пришли кадр — покажу ошибки композиции, света и настроения "
            "прямо на снимке. <b>Бесплатно, 5 раз в день.</b>\n\n"
            "✨ <b>Улучшение фото</b>\n"
            "ИИ исправит композицию, свет, уберёт лишнее, дорисует края. "
            "На основе анализа — точно и по делу.\n\n"
            "🎨 <b>Создание изображения</b>\n"
            "Нарисуй картинку по описанию — с нуля или на основе своего фото. "
            "На современной модели <i>Nano Banana 2</i> от Google.\n\n"
            "🎉 <b>Праздники</b>\n"
            "Новогодние и свадебные фотосессии, пригласительные открытки, "
            "день рождения — с сохранением лиц.\n\n"
            "🛠 <b>Инструменты</b>\n"
            "Редактор, Flat Lay, стилизация, фото на документы, "
            "студийный портрет, «по референсу» из Pinterest.\n\n"
            "🎓 <b>Мини-курс по композиции (10 дней)</b>\n"
            "С проверкой заданий. Первый день — бесплатно.\n\n"
            "🔮 <b>Карта дня</b>\n"
            "Мистический ритуал с фотографией — послание и задание на день.\n\n"
            f"💎 <b>Твой баланс:</b> {balance_text} генераций\n\n"
            "Присылай фото — или начни с разбора 👇"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎉 Праздники", callback_data="holidays_start")],
            [InlineKeyboardButton(text="🔮 Карта дня", callback_data="daily_card")],
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="🛠 Инструменты", callback_data="tools_menu")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💎 Баланс", callback_data="my_balance")],
            [InlineKeyboardButton(text="💛 Поддержать проект", callback_data="donate_menu")],
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
    _save_test_mode()
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
@dp.callback_query(F.data.startswith("new_photo_same_"))
async def handle_new_photo_same(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[-1])
    flat_lay_active[user_id] = False

    # Если пришли из Редактора — остаёмся в Редакторе
    if editor_mode.get(user_id):
        user_mode[user_id] = "change_format"
        await callback.answer()
        await callback.message.answer(
            "✂️ Пришли новое фото для редактора.",
            parse_mode="HTML"
        )
        return

    # Иначе — как раньше (возврат в анализ)
    await callback.answer()
    await callback.message.answer("Просто пришли новое фото.", parse_mode="HTML")


@dp.callback_query(F.data == "new_photo")
async def handle_new_photo(callback: CallbackQuery):
    _reset_all_flows(callback.from_user.id)
    user_mode[callback.from_user.id] = "free"
    flat_lay_active[callback.from_user.id] = False
    style_active.pop(callback.from_user.id, None)
    editor_mode.pop(callback.from_user.id, None)
    await callback.message.answer("Присылай фото — жду! 📷")
    await callback.answer()


@dp.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    reset_xmas_state(callback.from_user.id)
    reset_ref_state(callback.from_user.id)
    reset_daily_state(callback.from_user.id)
    user_mode[callback.from_user.id] = "free"
    flat_lay_active[callback.from_user.id] = False
    style_active.pop(callback.from_user.id, None)
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    editor_mode.pop(callback.from_user.id, None)
    balance = get_balance(callback.from_user.id)
    balance_text = "∞" if (callback.from_user.id == 456504792 and test_mode) else str(balance)

    await callback.message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
        caption=(
            "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
            "📸 <b>Разбор фото</b> — бесплатно, 5 раз в день.\n"
            "✨ <b>Улучшение фото</b> — ИИ исправит по анализу.\n"
            "🎨 <b>Создание изображения</b> — по описанию или по фото.\n"
            "🎉 <b>Праздники</b> — новогодние, свадьба, день рождения.\n"
            "🛠 <b>Инструменты</b> — редактор, Flat Lay, стилизация и другое.\n"
            "🎓 <b>Мини-курс</b> — первый день бесплатно.\n"
            "🔮 <b>Карта дня</b> — послание и задание.\n\n"
            f"💎 <b>Твой баланс:</b> {balance_text} генераций"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎉 Праздники", callback_data="holidays_start")],
            [InlineKeyboardButton(text="🔮 Карта дня", callback_data="daily_card")],
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="🛠 Инструменты", callback_data="tools_menu")],
            [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
            [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
            [InlineKeyboardButton(text="💎 Баланс", callback_data="my_balance")],
            [InlineKeyboardButton(text="💛 Поддержать проект", callback_data="donate_menu")],
            [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
        ])
    )


@dp.callback_query(F.data == "tools_menu")
async def handle_tools_menu(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    reset_xmas_state(callback.from_user.id)
    reset_ref_state(callback.from_user.id)
    reset_daily_state(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "free"
    flat_lay_active[user_id] = False
    style_active.pop(user_id, None)
    balance = get_balance(user_id)
    editor_mode.pop(user_id, None)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)
    await callback.message.answer(
        f"🛠 <b>Инструменты</b>\n\n"
        f"💎 Твой баланс: {balance_text}\n\n"
        "Выбери инструмент:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
            [InlineKeyboardButton(text="📷 Flat Lay (предметная съёмка)", callback_data="flat_lay")],
            [InlineKeyboardButton(text="🎨 Стилизация", callback_data="style_photo")],
            [InlineKeyboardButton(text="🖼️ По референсу (Pinterest)", callback_data="ref_style")],
            [InlineKeyboardButton(text="🎨 Создать изображение", callback_data="prompt_start")],
            [InlineKeyboardButton(text="📄 Фото на документы", callback_data="doc_photo")],
            [InlineKeyboardButton(text="🧑💼 Студийный портрет", callback_data="studio_portrait")],
        ])
    )


@dp.callback_query(F.data == "author_info")
async def handle_author_info(callback: CallbackQuery):
    await callback.message.answer(
        "📸 <b>Евгений Севостьянов</b>\n"
        "Фотограф, преподаватель.\n\n"
        "📷 Instagram: @sevosphoto\n"
        "💬 Telegram: @sevosphoto\n"
        "🌐 VK: @cevoc\n\n"
        "━━━━━━━━━━━━━━━\n"
        "ИП Севостьянов Евгений Александрович\n"
        "ИНН: 701741776350\n"
        "Оплата через банк Точка",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "my_balance")
async def handle_my_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    free_analyses = _analysis_get_free_left(user_id)
    paid_analyses_left = paid_analyses.get(user_id, 0)
    free_text = "∞" if (user_id == 456504792 and test_mode) else str(free_analyses)

    text = (
        f"💎 <b>Твой баланс</b>\n\n"
        f"⚡ <b>Генерации:</b> {balance_text}\n"
        f"1 генерация = 1 результат в любом инструменте.\n"
        f"В каждой — 1 бесплатная перегенерация.\n\n"
        f"🔍 <b>Анализы:</b>\n"
        f"Бесплатных сегодня: <b>{free_text}</b>\n"
        f"В запасе (платные): <b>{paid_analyses_left}</b>\n"
        f"Платные не сгорают — тратятся, когда кончится бесплатный лимит.\n\n"
        f"Пополни:"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=balance_keyboard())
    await callback.answer()


# ===== РЕДАКТОР =====
@dp.callback_query(F.data == "style_photo")
async def handle_style_photo_inline(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "style_photo"
    flat_lay_active[user_id] = False
    style_active.pop(user_id, None)
    balance = get_balance(user_id)
    await callback.message.answer(
        f"🎨 <b>Стилизация</b>\n\n"
        f"Пришли фото — сделаю стильным.\n"
        f"Доступно 14 художественных стилей + свой.\n\n"
        f"💰 Стоимость: 1 генерация\n"
        f"💎 Твой баланс: {balance}",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "doc_photo")
async def handle_doc_photo(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "doc_photo"
    balance = get_balance(user_id)
    await callback.message.answer(
        f"📄 <b>Фото на документы</b>\n\n"
        f"Сделаю аккуратный документ: белый фон, деловой образ, лёгкая ретушь.\n\n"
        f"💰 Стоимость: 1 генерация\n"
        f"💎 Твой баланс: {balance}\n\n"
        "Вот пример — как преображается фото:",
        parse_mode="HTML"
    )
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    # Фото ДО
    try:
        await callback.message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/examples/doc_photo/before.jpg"),
            caption="📷 <b>ДО</b> — обычное фото",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить before.jpg: {e}")
    # Фото ПОСЛЕ
    try:
        await callback.message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/examples/doc_photo/after.jpg"),
            caption="✨ <b>ПОСЛЕ</b> — фото на документы",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить after.jpg: {e}")
    # Кнопки
    await callback.message.answer(
        "Перед съёмкой ознакомься с инструкцией или сразу загружай фото.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Показать инструкцию", callback_data="doc_instruction")],
            [InlineKeyboardButton(text="📸 Я готов — загрузить фото", callback_data="doc_ready")],
        ])
    )


@dp.callback_query(F.data == "doc_instruction")
async def handle_doc_instruction(callback: CallbackQuery):
    await callback.answer()
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    await callback.message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/doc_instruction.jpg"),
        caption=(
            "📸 <b>Как сфотографировать себя на телефон:</b>\n\n"
            "1. Протрите объектив камеры мягкой тканью\n"
            "2. Встаньте напротив окна, свет на лицо\n"
            "3. Телефон на уровне глаз\n"
            "4. Смотрите прямо в камеру\n"
            "5. Уберите волосы с лица\n"
            "6. Нейтральное выражение, рот закрыт\n"
            "7. Очки — только прозрачные линзы"
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "doc_ready")
async def handle_doc_ready(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    if balance <= 0 and not (user_id == 456504792 and test_mode):
        await callback.message.answer(
            "💎 Генерации закончились.\n\nПополни баланс:",
            reply_markup=buy_generations_keyboard()
        )
        return
    user_mode[user_id] = "doc_type"
    await callback.message.answer(
        "📄 <b>Выберите тип документа:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Паспорт РФ (35×45 мм)", callback_data="doctype_passport")],
            [InlineKeyboardButton(text="📇 Документы (30×40 мм)", callback_data="doctype_3x4")],
        ])
    )


@dp.callback_query(F.data.startswith("doctype_"))
async def handle_doctype(callback: CallbackQuery):
    doc_type = callback.data.split("_", 1)[1]
    user_id = callback.from_user.id
    doc_type_last[user_id] = doc_type
    user_mode[user_id] = f"doc_photo_{doc_type}"
    await callback.answer()
    await callback.message.answer(
        "📸 Пришлите фото в анфас.\n\n"
        "Очки оставим без изменений."
    )


@dp.callback_query(F.data == "change_format")
async def handle_change_format(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "change_format"
    flat_lay_active[user_id] = False
    editor_mode[user_id] = True
    balance = get_balance(user_id)
    await callback.message.answer(
        f"✂️ <b>Редактор</b>\n\n"
        f"Загрузи фото и работай без анализа: меняй формат, улучшай, ретушируй, стилизуй.\n\n"
        f"💰 Стоимость: 1 генерация\n"
        f"💎 Твой баланс: {balance}\n\n"
        "Просто пришли фото.",
        parse_mode="HTML"
    )


# ===== СТУДИЙНЫЙ ПОРТРЕТ =====
@dp.callback_query(F.data == "studio_portrait")
async def handle_studio_portrait(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "studio_portrait"
    balance = get_balance(user_id)
    await callback.message.answer(
        f"🧑💼 <b>Студийный портрет</b>\n\n"
        f"Сделаю студийный портрет: мягкий свет, красивый фон, аккуратный образ.\n\n"
        f"💰 Стоимость: 1 генерация\n"
        f"💎 Твой баланс: {balance}\n\n"
        "Вот пример — как преображается фото:",
        parse_mode="HTML"
    )
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    try:
        await callback.message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/examples/studio_portrait/before.jpg"),
            caption="📷 <b>ДО</b> — обычное фото",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить before.jpg: {e}")
    try:
        await callback.message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/examples/studio_portrait/after.jpg"),
            caption="✨ <b>ПОСЛЕ</b> — студийный портрет",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить after.jpg: {e}")
    await callback.message.answer(
        "Перед съёмкой ознакомься с инструкцией или сразу загружай фото.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Показать инструкцию", callback_data="studio_instruction")],
            [InlineKeyboardButton(text="📸 Я готов — загрузить фото", callback_data="studio_ready")],
        ])
    )


@dp.callback_query(F.data == "studio_instruction")
async def handle_studio_instruction(callback: CallbackQuery):
    await callback.answer()
    PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
    await callback.message.answer_photo(
        URLInputFile(f"{PHOTO_BASE}/doc_instruction.jpg"),
        caption=(
            "📸 <b>Как сфотографировать себя на телефон:</b>\n\n"
            "1. Протрите объектив камеры мягкой тканью\n"
            "2. Встаньте напротив окна, свет на лицо\n"
            "3. Телефон на уровне глаз\n"
            "4. Смотрите прямо в камеру\n"
            "5. Уберите волосы с лица\n"
            "6. Нейтральное выражение, рот закрыт\n"
            "7. Очки — только прозрачные линзы"
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "studio_ready")
async def handle_studio_ready(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    if balance <= 0 and not (user_id == 456504792 and test_mode):
        await callback.message.answer(
            "💎 Генерации закончились.\n\nПополни баланс:",
            reply_markup=buy_generations_keyboard()
        )
        return
    user_mode[user_id] = "studio_angle"
    await callback.message.answer(
        f"✅ Осталось генераций: {balance}\n\n"
        "Пришлите фото.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("angle_"))
async def handle_studio_angle(callback: CallbackQuery):
    angle = callback.data.split("_")[1]
    user_id = callback.from_user.id
    studio_angle_choice[user_id] = angle
    user_mode[user_id] = "studio_bg"
    await callback.answer()
    await callback.message.answer(
        "🎨 <b>Выберите фон:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚪ Белый", callback_data="bg_white")],
            [InlineKeyboardButton(text="🔘 Светло-серый", callback_data="bg_lightgray")],
            [InlineKeyboardButton(text="🔵 Голубой", callback_data="bg_blue")],
            [InlineKeyboardButton(text="🔷 Синий", callback_data="bg_darkblue")],
            [InlineKeyboardButton(text="⬛ Чёрный", callback_data="bg_black")],
        ])
    )


@dp.callback_query(F.data.startswith("bg_"))
async def handle_studio_bg(callback: CallbackQuery):
    bg = callback.data.split("_")[1]
    user_id = callback.from_user.id
    studio_bg_choice[user_id] = bg
    user_mode[user_id] = "studio_outfit"
    await callback.answer()
    await callback.message.answer(
        "👔 <b>Выберите стиль одежды:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👕 Своя одежда", callback_data="studio_outfit_own")],
            [InlineKeyboardButton(text="👔 Деловой стиль", callback_data="studio_outfit_business")],
            [InlineKeyboardButton(text="🧥 Свободный стиль", callback_data="studio_outfit_casual")],
        ])
    )


@dp.callback_query(F.data.startswith("studio_outfit_"))
async def handle_studio_outfit(callback: CallbackQuery):
    outfit = callback.data.split("_")[2]
    user_id = callback.from_user.id
    studio_outfit_choice[user_id] = outfit
    await callback.answer()
    await callback.message.answer(
        "💇 <b>Выберите причёску:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оставить как есть", callback_data="studio_hair_keep")],
            [InlineKeyboardButton(text="Аккуратная укладка", callback_data="studio_hair_neat")],
            [InlineKeyboardButton(text="Лёгкая коррекция", callback_data="studio_hair_fix")],
        ])
    )


@dp.callback_query(F.data.startswith("studio_hair_"))
async def handle_studio_hair(callback: CallbackQuery):
    hair = callback.data.split("_")[2]
    user_id = callback.from_user.id
    studio_hair_choice[user_id] = hair

    angle = studio_angle_choice.get(user_id, "front")
    bg = studio_bg_choice.get(user_id, "white")
    outfit = studio_outfit_choice.get(user_id, "own")

    angle_names = {"front": "анфас", "half": "полуоборот"}
    bg_names = {"white": "белый", "lightgray": "светло-серый", "blue": "голубой", "darkblue": "синий", "black": "чёрный"}
    outfit_names = {
        "own": "оставить СВОЮ одежду с исходного фото без изменений — тот же цвет, фасон, детали",
        "business": "деловой стиль — рубашка и пиджак",
        "casual": "свободный стиль — футболка или свитер, джинсы",
    }
    hair_names = {"keep": "оставить причёску как есть", "neat": "аккуратная укладка", "fix": "лёгкая коррекция причёски"}

    prompt = (
        f"Студийный портрет по грудь. "
        f"Ракурс: {angle_names.get(angle, angle)}. "
        f"При полуобороте взгляд направлен в камеру. "
        f"Фон: {bg_names.get(bg, bg)} с мягкой красивой тенью. "
        f"ОДЕЖДА: {outfit_names.get(outfit, outfit)}. "
        f"СТРОГО ТОЛЬКО ЭТА ОДЕЖДА — не добавляй другие предметы одежды. "
        f"Причёска: {hair_names.get(hair, hair)}. "
        f"Лёгкая естественная ретушь кожи. "
        f"Студийный свет, объём, мягкие тени. "
        f"Сохранить черты лица. Не менять лицо. "
        f"Портрет по грудь: голова и верхняя часть плеч."
    )
    gen_wish[user_id] = prompt
    gen_format[user_id] = "original"
    flat_lay_active[user_id] = False
    user_mode[user_id] = "studio_format"
    await callback.answer()
    await callback.message.answer(
        "📐 <b>Выбери формат портрета:</b>",
        parse_mode="HTML",
        reply_markup=portrait_format_keyboard()
    )


@dp.callback_query(F.data.startswith("pformat_"))
async def handle_portrait_format(callback: CallbackQuery):
    fmt = callback.data.replace("pformat_", "")
    user_id = callback.from_user.id
    gen_format[user_id] = fmt
    user_mode[user_id] = "studio_portrait_generating"
    ratio_text = {"1_1": "1:1 (квадрат)", "3_4": "3:4 (вертикаль)", "4_3": "4:3 (горизонт)",
                  "4_5": "4:5 (Instagram)", "9_16": "9:16 (сторис)", "original": "как исходное фото"}.get(fmt, "как исходное")
    old_wish = gen_wish.get(user_id, "")
    gen_wish[user_id] = (
        f"{old_wish} "
        f"ВАЖНО: верни изображение СТРОГО в формате {ratio_text}. "
        f"Композиция должна быть выстроена именно под этот формат. "
        f"Голова должна быть ПОЛНОСТЬЮ видна — не обрезай макушку, подбородок, плечи."
    )
    await callback.answer("🎨 Создаю портрет...")
    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("studio_retry_"))
async def handle_studio_retry(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])

    if gen_retry_count.get(user_id, 0) >= 1:
        await callback.answer("Лимит перегенераций исчерпан.", show_alert=True)
        return

    saved_wish = last_prompt.get(user_id, "")
    saved_fmt = last_format.get(user_id, "")
    if saved_wish:
        gen_wish[user_id] = saved_wish
    if saved_fmt:
        gen_format[user_id] = saved_fmt

    old_photo = last_photo.get(user_id)

    # ВАЖНО: ставим режим studio_, чтобы do_generation показал правильные кнопки
    user_mode[user_id] = "studio_retry"

    await callback.answer("🔄 Перегенерирую...")
    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False, mode="retry")

    new_photo = last_photo.get(user_id)
    if new_photo != old_photo:
        gen_retry_count[user_id] = 1


@dp.callback_query(F.data.startswith("studio_next_"))
async def handle_studio_next(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await callback.answer()
    user_mode[user_id] = "studio_angle"
    balance = get_balance(user_id)
    await callback.message.answer(
        f"✅ Осталось генераций: {balance}\n\n"
        "Пришлите новое фото.",
        parse_mode="HTML"
    )


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
            [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]
        ])
    )


@dp.callback_query(F.data == "pay_author_review")
async def handle_pay_author_review(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(500, "Авторский разбор фото", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Не удалось создать ссылку.")
        return
    await callback.message.answer(
        "💳 <b>Авторский разбор — 500 ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.\n"
        "Это связано с сертификатами Минцифры.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 500 ₽", url=link)]
        ])
    )


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
    await callback.message.answer(
        f"💛 <b>Поддержать на {amount} ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "donate_100")
async def d100(c: CallbackQuery):
    await _handle_donate(c, 100)


@dp.callback_query(F.data == "donate_300")
async def d300(c: CallbackQuery):
    await _handle_donate(c, 300)


@dp.callback_query(F.data == "donate_500")
async def d500(c: CallbackQuery):
    await _handle_donate(c, 500)


# ===== ПОКУПКА ГЕНЕРАЦИЙ =====
@dp.callback_query(F.data == "show_buy_menu")
async def handle_show_buy_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💎 <b>Пополнение баланса</b>\n\n"
        "1 генерация = 1 результат в любом инструменте.\n"
        "В каждой — 1 бесплатная перегенерация.\n\n"
        "Выбери пакет:",
        parse_mode="HTML",
        reply_markup=buy_generations_keyboard()
    )

@dp.callback_query(F.data == "buy_30_analysis")
async def handle_buy_30_analysis(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(49, "Пакет 30 анализов", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "🔍 <b>+30 анализов — 49 ₽</b>\n\n"
        "Пакет не сгорает — тратится, когда кончится бесплатный лимит.\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 49 ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "buy_100_analysis")
async def handle_buy_100_analysis(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(129, "Пакет 100 анализов", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "🔍 <b>+100 анализов — 129 ₽</b>\n\n"
        "Пакет не сгорает — тратится, когда кончится бесплатный лимит.\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 129 ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "buy_300_analysis")
async def handle_buy_300_analysis(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(299, "Пакет 300 анализов", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "🔍 <b>+300 анализов — 299 ₽</b>\n\n"
        "Пакет не сгорает — тратится, когда кончится бесплатный лимит.\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 299 ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "buy_5_gen")
async def handle_buy_5_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(59, "Пакет 5 генераций", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "⚡ <b>5 генераций — 59 ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 59 ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "buy_10_gen")
async def handle_buy_10_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(99, "Пакет 10 генераций", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "⚡ <b>10 генераций — 99 ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 99 ₽", url=link)]
        ])
    )


@dp.callback_query(F.data == "buy_30_gen")
async def handle_buy_30_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(249, "Пакет 30 генераций", callback.from_user.id)
    if not link:
        await callback.message.answer("⚠️ Ошибка.")
        return
    await callback.message.answer(
        "⚡ <b>30 генераций — 249 ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 249 ₽", url=link)]
        ])
    )


# ===== ГЕНЕРАЦИЯ С ФОРМАТАМИ =====
def register_format_handlers():
    for fmt, name in FORMATS:
        def make_handler(fmt=fmt, name=name):
            @dp.callback_query(F.data == f"gen_{fmt}_paid")
            async def handler(callback: CallbackQuery):
                user_id = callback.from_user.id
                gen_format[user_id] = fmt
                flat_lay_active[user_id] = False
                if user_mode.get(user_id) == "change_format_only":
                    gen_wish[user_id] = (
                        "Только измени формат фото. "
                        "НЕ меняй позу человека, лицо, одежду. "
                        "Дорисуй или обрежь края."
                    )
                    await callback.answer("📐 Меняю формат...")
                    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False)
                    return
                await callback.answer()
                await callback.message.answer(
                    f"✨ Выбран формат: <b>{name}</b>\n\nЧто делаем?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✨ Улучшить", callback_data=f"gen_go_ok_paid_{user_id}")],
                        [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_go_pose_paid_{user_id}")],
                        [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_go_retouch_paid_{user_id}")],
                        [InlineKeyboardButton(text="📐 Только формат", callback_data=f"gen_go_format_only_paid_{user_id}")],
                        [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_paid_{user_id}")],
                    ]))
            return handler
        make_handler()


register_format_handlers()


@dp.callback_query(F.data == "gen_start")
async def handle_gen_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото!")
        return
    await callback.answer()
    await callback.message.answer(
        "✨ <b>Улучшение фото</b>\n\nВыбери формат:",
        parse_mode="HTML",
        reply_markup=format_keyboard("paid")
    )


# ===== ОБРАБОТЧИКИ ДЕЙСТВИЙ ГЕНЕРАЦИИ =====
def _build_analysis_prompt(user_id: int) -> str:
    """Собирает промпт на основе результатов анализа фото."""
    analysis = last_analysis.get(user_id, {})
    error_type = analysis.get("error_type", "")
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")

    parts = [
        "Ты — профессиональный фотограф-наставник с 20-летним опытом. "
        "Твоя задача — переснять этот кадр так, как его снял бы мастер. "
        "Результат — тот же кадр, но с идеальной композицией, светом и настроением. "
        "\n\n"
        "═══ ЧТО ИСПРАВИТЬ ПО АНАЛИЗУ ═══\n"
    ]

    if what_is_wrong and what_is_wrong != "---":
        parts.append(f"ОШИБКА КАДРА: {what_is_wrong}. ")
    if how_to_fix and how_to_fix != "---":
        parts.append(f"КАК ИСПРАВИТЬ: {how_to_fix}. ")

    if "horizon" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО выровняй горизонт до идеально ровного. ")
    if "thirds" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО примени правило третей — смести главный объект к одной из третей кадра, добавь воздуха. ")
    if "distortion" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО исправь дисторсию и завалы по краям кадра. ")
    if "pose" in error_type:
        parts.append("Сделай позу человека естественнее и изящнее, но не меняй её кардинально. ")
    if "lighting" in error_type:
        parts.append("Исправь освещение: убери пересветы, вытяни тени, сделай свет мягче и объёмнее. ")
    if "shadow" in error_type:
        if "художественный" not in (what_is_wrong or "").lower():
            parts.append("Убери тень фотографа и лишние тени. ")
        else:
            parts.append("Сохрани художественную тень как задумано автором. ")
    if "cropping" in error_type:
        parts.append("Обрежь лишнее по краям, выстрой аккуратную композицию. ")
    if "framing" in error_type:
        parts.append("Улучши фрейминг: сделай кадр цельным, без обрезов по конечностям. ")
    if "fill_frame" in error_type:
        parts.append("Заполни кадр гармонично — объект не должен быть потерян в пустоте. ")
    if "leading_lines" in error_type:
        parts.append("Используй ведущие линии для усиления композиции. ")
    if "balance" in error_type:
        parts.append("Улучши баланс кадра — не должно перевешивать в одну сторону. ")
    if "rhythm" in error_type:
        parts.append("Усиль ритм и перспективу в кадре. ")

    parts.append(
        "\n\n═══ ПРОФЕССИОНАЛЬНЫЙ ЧЕК-ЛИСТ ═══\n"
        "Пройдись по каждому пункту, даже если в анализе не указано:\n"
        "• Горизонт идеально ровный? Если хоть чуть завален — выровняй.\n"
        "• Правило третей: объект осознанно стоит? Если случайно в центре — смести.\n"
        "• Воздух по направлению взгляда есть? Если нет — добавь.\n"
        "• Свет: есть объём, или плоский? Если плоский — сделай светотень.\n"
        "• Тени: работают на форму? Если нет — переделай.\n"
        "• Баланс: не перевешивает? Если да — выровняй.\n"
        "• Фрейминг: цельный, без обрезов конечностей? Если нет — поправь.\n"
        "• Перспектива: не искажает? Если да — исправь.\n"
        "• Цвета: не пересвечены? Вытяни.\n"
        "• Фон: не мешает главному? Почисти.\n"
        "• Поза: живая или зажатая? Слегка поправь, если зажата.\n"
        "• Эмоция: живая или пустая? Слегка добавь живости, не переигрывай.\n"
        "• Мусор в кадре? Убери.\n"
        "• Ритм, линии, симметрия — усиль, если возможно.\n"
    )

    parts.append(
        "\n\n═══ ЧТО СОХРАНИТЬ ЖЁСТКО ═══\n"
        "• Количество людей — ТОЧНО как на фото. НЕ добавляй ни одного. НЕ убирай ни одного.\n"
        "• Лица, черты лица, мимика — в точности как на фото.\n"
        "• ГЛАЗА: сохрани цвет радужки, форму, разрез, размер зрачков, "
        "форму и расположение бликов в точности как на исходном фото. "
        "НЕ добавляй блики, которых нет. НЕ увеличивай глаза. НЕ делай «кукольными». "
        "НЕ меняй взгляд.\n"
        "• ПОЗА И ВЗГЛЯД — ГЛАВНОЕ ПРАВИЛО: сохрани направление взгляда и поворот "
        "головы в точности как на исходном фото. "
        "Если человек смотрит в сторону — он смотрит в ту же сторону. "
        "Если смотрит на другого человека — продолжает смотреть на него. "
        "Если в профиль — остаётся в профиль. "
        "НЕ разворачивай людей в камеру. НЕ заставляй их смотреть в объектив. "
        "НЕ меняй положение корпуса и рук кардинально — только делай позу "
        "естественнее и гармоничнее, если она зажата. "
        "Сохрани осанку и посадку головы.\n"
        "• Одежда, причёска, аксессуары — в точности как на фото.\n"
        "• Предметы, машины, натюрморты — всё, что было в кадре, остаётся. "
        "НЕ добавляй новых объектов. НЕ убирай существующие. "
        "Памятники, скульптуры, архитектура, деревья, фонари — это часть кадра, "
        "они остаются. НЕ принимай их за людей. НЕ удаляй их.\n"
        "• Сюжет и смысл кадра — сохрани.\n"
        "• СРЕДА И ФАКТУРЫ — НЕ МЕНЯЙ. Если в кадре асфальт — оставь асфальт, "
        "не превращай в плитку. Если трава — оставь траву. Если доски — оставь доски. "
        "НЕ придумывай «красивые» замены. Среда — часть исходного кадра.\n"
    )

    parts.append(
        "\n\n═══ ДОРИСОВКА (если обрезано краем) ═══\n"
        "Верхнюю одежду не меняй. "
        "Если дорисовываешь низ — современно: "
        "брюки прямые, свободные, широкие джинсы, чиносы. "
        "Платье прямого силуэта, миди. "
        "Обувь по контексту: улица — обувь, дом или пляж — можно без. "
        "Фигуру и телосложение сохрани КАК НА ФОТО — "
        "если человек не беременный, живот не добавляй; "
        "свободная одежда — это оверсайз, а не беременность. "
        "Выражение лица не меняй."
    )

    parts.append(
        "\n\n═══ УБРАТЬ ТОЛЬКО ЯВНЫЙ МУСОР (АККУРАТНО) ═══\n"
        "Если в кадре есть явные помехи — убери их:\n"
        "• Провода, столбы, ветки, фонарные столбы, деревья, знаки, углы зданий — "
        "всё, что «торчит» из головы или тела человека. "
        "ОБЯЗАТЕЛЬНО удали их, даже если анализ их не упомянул.\n"
        "• Случайные прохожие на заднем плане.\n"
        "• Урны, объявления, случайные предметы, портящие фон.\n"
        "• Пятна, случайные блики на объективе, мусор.\n\n"
        "КАК УБИРАТЬ — ГЛАВНОЕ ПРАВИЛО:\n"
        "НЕ затирай объект однотонным пятном. НЕ оставляй размытый участок. "
        "НЕ оставляй пустое место. "
        "Вместо этого — ВОССТАНОВИ ФОН на месте объекта: "
        "дорисуй то, что ТАМ БЫЛО: если за столбом асфальт — асфальт, "
        "если деревья — деревья, если небо — небо. "
        "Сохрани ТУ ЖЕ фактуру, ТОТ ЖЕ материал — не меняй асфальт на плитку, "
        "не меняй траву на газон, не меняй доски на паркет. "
        "Сохрани фактуру фона, направление света, цвет, размытие (боке), "
        "перспективу. "
        "Результат должен выглядеть так, как будто объекта там НИКОГДА НЕ БЫЛО. "
        "Никаких следов удаления, никаких пятен, никаких размытых зон.\n\n"
        "Остальные объекты сцены — НЕ трогай. "
        "Памятники, скульптуры, архитектура, фонари, деревья, здания — "
        "это часть сцены, они остаются. "
        "НЕ принимай их за людей. НЕ удаляй их.\n"
    )

    parts.append(
        "\n\n═══ ФИНАЛ ═══\n"
        "Результат — тот же кадр, но снятый профессиональным фотографом. "
        "Гармоничный, красивый, с правильной композицией. "
        "При этом — с тем же человеком, той же одеждой, тем же сюжетом. "
        "Изменения ЗАМЕТНЫЕ, но исходный замысел сохранён."
    )

    return "".join(parts)

    # Конкретные ошибки из анализа
    if what_is_wrong and what_is_wrong != "---":
        parts.append(f"КОНКРЕТНАЯ ОШИБКА КАДРА: {what_is_wrong}. ")

    if how_to_fix and how_to_fix != "---":
        parts.append(f"КАК ИСПРАВИТЬ: {how_to_fix}. ")

    # Подсказки по типу ошибки
    if "horizon" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО выровняй горизонт до идеально ровного. ")
    if "thirds" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО примени правило третей — смести главный объект к одной из третей кадра, добавь воздуха. ")
    if "distortion" in error_type:
        parts.append("ОБЯЗАТЕЛЬНО исправь дисторсию и завалы по краям кадра. ")
    if "pose" in error_type:
        parts.append("Сделай позу человека естественнее и изящнее, но не меняй её кардинально. ")
    if "lighting" in error_type:
        parts.append("Исправь освещение: убери пересветы, вытяни тени, сделай свет мягче и объемнее. ")
    if "shadow" in error_type:
        if "художественный" not in (what_is_wrong or "").lower():
            parts.append("Убери тень фотографа и лишние тени. ")
        else:
            parts.append("Сохрани художественную тень как задумано автором. ")
    if "cropping" in error_type:
        parts.append("Обрежь лишнее по краям, выстрой аккуратную композицию. ")
    if "framing" in error_type:
        parts.append("Улучши фрейминг: сделай кадр цельным, без обрезов по конечностям. ")
    if "fill_frame" in error_type:
        parts.append("Заполни кадр гармонично — объект не должен быть потерян в пустоте. ")

    parts.append(
        "ДОРИСОВКА (если обрезано краем): "
        "Верхнюю одежду не меняй. "
        "Если дорисовываешь низ — современно: "
        "брюки прямые, свободные, широкие джинсы, чиносы. "
        "Платье прямого силуэта, миди. "
        "Обувь по контексту: улица — обувь, дом или пляж — можно без. "
        "Фигуру и телосложение сохрани КАК НА ФОТО — "
        "если человек не беременный, живот не добавляй; "
        "свободная одежда — это оверсайз, а не беременность. "
        "Выражение лица не меняй."
    )

    parts.append("Сделай изменения ЗАМЕТНЫМИ, но не разрушай исходный замысел. ")
    return "".join(parts)


@dp.callback_query(F.data.startswith("gen_go_ok_"))
async def handle_gen_go_ok(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()

    analysis = last_analysis.get(user_id, {})
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")

    # Что будет сделано — на основе анализа
    detail = ""
    if what_is_wrong and what_is_wrong != "---":
        detail += f"\n\n🎯 <b>На основе анализа:</b>\n{what_is_wrong}"
    if how_to_fix and how_to_fix != "---":
        detail += f"\n\n💡 <b>Как исправить:</b>\n{how_to_fix}"

    text = (
        "✨ <b>Улучшить фото</b>\n\n"
        "ИИ исправит ошибки композиции, света и цвета, "
        "которые были найдены в анализе:\n"
        "• Выровняет горизонт\n"
        "• Улучшит свет и тени\n"
        "• Исправит композицию по правилу третей\n"
        "• Уберёт случайный мусор с фона\n"
        "• Сделает цвета естественнее\n\n"
        "💾 <b>Что сохранится:</b>\n"
        "• Все люди, их лица, причёски, одежда\n"
        "• Сюжет и атмосфера кадра\n"
        "• Объекты с исходного фото\n"
        f"{detail}\n\n"
        "⚠️ <b>Важно:</b> ИИ не всегда точно понимает замысел автора "
        "и может ошибаться. Результат — художественная обработка, "
        "а не 100% гарантия. Если что-то не понравится — можно "
        "перегенерировать бесплатно.\n\n"
        "💰 Стоимость: 1 генерация"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Улучшить", callback_data=f"confirm_ok_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ])
    )


@dp.callback_query(F.data.startswith("confirm_ok_"))
async def handle_confirm_ok(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[2]
    user_id = int(parts[3])
    gen_wish[user_id] = _build_analysis_prompt(user_id)
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_deep_"))
async def handle_gen_go_deep(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    analysis = last_analysis.get(user_id, {})
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")
    base = _build_analysis_prompt(user_id)
    gen_wish[user_id] = (
        f"{base} "
        f"Сделай ГЛУБОКОЕ улучшение — обработай кадр тщательно. "
        f"{'Конкретно: ' + what_is_wrong + '. ' if what_is_wrong and what_is_wrong != '---' else ''}"
        f"{'Решение: ' + how_to_fix + '. ' if how_to_fix and how_to_fix != '---' else ''}"
        f"Изменения должны быть ОЧЕНЬ заметными. "
    )
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_full_"))
async def handle_gen_go_full(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()

    analysis = last_analysis.get(user_id, {})
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")

    detail = ""
    if what_is_wrong and what_is_wrong != "---":
        detail += f"\n\n🎯 <b>На основе анализа:</b>\n{what_is_wrong}"
    if how_to_fix and how_to_fix != "---":
        detail += f"\n\n💡 <b>Как исправить:</b>\n{how_to_fix}"

    text = (
        "🎨 <b>Полная переработка</b>\n\n"
        "ИИ заново выстроит кадр — это заметное изменение, а не лёгкая правка:\n"
        "• Перестроит композицию по правилу третей\n"
        "• Изменит позу и положение людей\n"
        "• Полностью переработает свет\n"
        "• Заменит или улучшит фон\n"
        "• Сделает кадр кинематографичнее\n\n"
        "💾 <b>Что сохранится:</b>\n"
        "• Все люди с исходного фото\n"
        "• Черты лиц, причёски, одежда\n"
        "• Сюжет и общий замысел\n"
        f"{detail}\n\n"
        "⚠️ <b>Важно:</b> полная переработка сильно меняет кадр. "
        "ИИ может не угадать с замыслом или деталями. "
        "Результат — художественная интерпретация, а не 100% точность. "
        "Если что-то не понравится — 1 бесплатная перегенерация.\n\n"
        "💰 Стоимость: 1 генерация"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Переработать", callback_data=f"confirm_full_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ])
    )


@dp.callback_query(F.data.startswith("confirm_full_"))
async def handle_confirm_full(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[2]
    user_id = int(parts[3])
    analysis = last_analysis.get(user_id, {})
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")
    gen_wish[user_id] = (
        f"Полностью переработай кадр: композицию, позу, фон, свет. "
        f"СОХРАНИ идею и сюжет исходного фото. "
        f"СОХРАНИ всех людей, их лица, причёски. "
        f"Верхнюю одежду не меняй. "
        f"Если дорисовываешь низ — современно: "
        f"брюки прямые, свободные, широкие джинсы, чиносы. "
        f"Платье прямого силуэта, миди. "
        f"Обувь по контексту. "
        f"Фигуру сохрани как на фото. "
        f"НЕ добавляй новых людей и объектов. "
        f"{'Исправь ошибку: ' + what_is_wrong + '. ' if what_is_wrong and what_is_wrong != '---' else ''}"
        f"{'Решение: ' + how_to_fix + '. ' if how_to_fix and how_to_fix != '---' else ''}"
        f"Сделай кадр значительно красивее и гармоничнее. "
    )
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_pose_"))
async def handle_gen_go_pose(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Сфокусируйся ТОЛЬКО на позе: сделай её изящнее. НЕ меняй фон."
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_repose_"))
async def handle_gen_go_repose(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = (
        "Измени позу: разверни корпус, измени руки и ноги. "
        "Сохрани лицо и верхнюю одежду. "
        "Если дорисовываешь низ — современно: "
        "брюки прямые, свободные, широкие джинсы, чиносы. "
        "Платье прямого силуэта, миди. "
        "Обувь по контексту: улица — обувь, дом — можно без. "
        "Фигуру сохрани как на фото."
    )
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_retouch_"))
async def handle_gen_go_retouch(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()

    text = (
        "💫 <b>Ретушь портрета</b>\n\n"
        "Что будет сделано:\n"
        "• Сглаживание морщин и складок на лице и шее\n"
        "• Убраны тёмные круги и мешки под глазами\n"
        "• Убраны покраснения и пигментные пятна\n"
        "• Смягчены резкие тени на лице\n"
        "• Осветлён и очищен взгляд\n"
        "• Причёска станет аккуратнее\n\n"
        "💾 <b>Что НЕ изменится:</b>\n"
        "• Черты лица, форма носа, губ, разрез глаз\n"
        "• Фон, одежда, поза, свет, композиция\n"
        "• Естественная текстура кожи (без «пластика»)\n\n"
        "⚠️ <b>Важно:</b> ИИ может ошибаться. Иногда ретушь "
        "получается слишком сильной или наоборот слабой. "
        "Результат — художественная обработка. "
        "Если что-то не понравится — 1 бесплатная перегенерация.\n\n"
        "💰 Стоимость: 1 генерация"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ретушировать", callback_data=f"confirm_retouch_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ])
    )


@dp.callback_query(F.data.startswith("confirm_retouch_"))
async def handle_confirm_retouch(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[2]
    user_id = int(parts[3])
    gen_wish[user_id] = (
        "Сделай ЗАМЕТНУЮ ПРОФЕССИОНАЛЬНУЮ РЕТУШЬ ПОРТРЕТА. "
        "Изменения должны быть ВИДНЫ сразу, а не едва уловимы. "
        "ЛИЦО: сгладь ВСЕ морщины и складки — лоб, носогубные, вокруг глаз. "
        "Убери тёмные круги и мешки под глазами ЗАМЕТНО. "
        "Выровняй тон кожи: убери покраснения, пигментные пятна, неровности. "
        "Смягчи резкие тени на лице. "
        "ГЛАЗА: осветли белки, убери красноту, сделай взгляд ярче, добавь блик. "
        "ВОЛОСЫ: убери выбившиеся волоски, сделай причёску аккуратной. "
        "ГУБЫ: сделай их чуть более выразительными, но естественными. "
        "СОХРАНИ черты лица, форму носа, губ, разрез глаз — не меняй человека. "
        "Кожа должна остаться естественной, с лёгкой текстурой, без «пластика». "
        "НЕ трогай фон, одежду, позу, свет, композицию. "
        "Сохрани всех людей с фото."
    )
    await callback.answer("Запускаю ретушь...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_horizon_"))
async def handle_gen_go_horizon(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    gen_wish[user_id] = "Только выровняй горизонт. Не меняй объекты, свет, композицию."
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_format_only_"))
async def handle_gen_go_format_only(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[4]
    user_id = int(parts[5])
    gen_wish[user_id] = "Только измени формат: дорисуй или обрежь края. НЕ меняй изображение."
    await callback.answer("Запускаю генерацию...")
    await do_generation(user_id, callback.message.chat.id, gen_type)
    user_mode[user_id] = "free"


@dp.callback_query(F.data.startswith("gen_go_custom_"))
async def handle_gen_go_custom(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    user_mode[user_id] = f"gen_wish_{gen_type}"
    await callback.answer()
    await callback.message.answer(
        "✏️ Напиши пожелание, например:\n"
        "• «убери провода и мусор»\n"
        "• «сделай свет мягче»\n"
        "• «дорисуй обрезанный край»"
    )


# ===== FLAT LAY =====
@dp.callback_query(F.data == "flat_lay")
async def handle_flat_lay(callback: CallbackQuery):
    await callback.answer()
    _reset_all_flows(callback.from_user.id)
    user_id = callback.from_user.id
    user_mode[user_id] = "flat_lay_format"
    flat_lay_active[user_id] = False
    balance = get_balance(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📐 Исходный формат", callback_data=f"flatfmt_original_{user_id}")],
        [InlineKeyboardButton(text="📱 1:1 (квадрат)", callback_data=f"flatfmt_1_1_{user_id}")],
        [InlineKeyboardButton(text="📱 4:5 (Instagram пост)", callback_data=f"flatfmt_4_5_{user_id}")],
        [InlineKeyboardButton(text="📱 9:16 (сториз)", callback_data=f"flatfmt_9_16_{user_id}")],
    ])
    if balance > 0 or (user_id == 456504792 and test_mode):
        await callback.message.answer(
            f"📷 <b>Flat Lay (предметная съёмка)</b>\n\n"
            f"Сфоткай предметы сверху или под небольшим углом.\n"
            f"Я распознаю их и сделаю стильную композицию.\n\n"
            f"💰 Стоимость: 1 генерация\n"
            f"💎 Твой баланс: {balance}\n\n"
            "Вот пример — как преображается кадр:",
            parse_mode="HTML"
        )
        PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
        try:
            await callback.message.answer_photo(
                URLInputFile(f"{PHOTO_BASE}/examples/flat_lay/before.jpg"),
                caption="📷 <b>ДО</b> — обычное фото",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить before.jpg: {e}")
        try:
            await callback.message.answer_photo(
                URLInputFile(f"{PHOTO_BASE}/examples/flat_lay/after.jpg"),
                caption="✨ <b>ПОСЛЕ</b> — стильный Flat Lay",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить after.jpg: {e}")
        await callback.message.answer(
            "Выбери формат:",
            reply_markup=keyboard
        )
    else:
        await callback.message.answer(
            "💎 Генерации закончились.\n\nПополни баланс:",
            reply_markup=buy_generations_keyboard()
        )


@dp.callback_query(F.data.startswith("flatfmt_"))
async def handle_flat_fmt(callback: CallbackQuery):
    parts = callback.data.split("_")
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
    style = parts[1]
    user_id = int(parts[2])
    if style not in FLAT_LAY_PROMPTS:
        await callback.answer("Неизвестный стиль")
        return
    gen_wish[user_id] = FLAT_LAY_PROMPTS[style]
    flat_lay_active[user_id] = True
    flat_lay_style[user_id] = style
    await callback.answer("🎨 Применяю стиль...")
    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False)
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
    gen_used_count[user_id] = 0
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
        f"ПОЛНОСТЬЮ перемешай предметы. "
        f"Распредели предметы гармонично. "
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
        "ПОЛНОСТЬЮ перемешай предметы. "
        "Добавь новые декоративные элементы в том же стиле. "
        "Сохрани все предметы с фото."
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
        "Сохрани все предметы с фото."
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
    gen_used_count[user_id] = 0
    flat_lay_active[user_id] = True
    await callback.answer()
    await callback.message.answer("✏️ Напиши пожелание для доработки:")


@dp.callback_query(F.data.startswith("flat_back_"))
async def handle_flat_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


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
        "Выбери инструмент.\n"
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


@dp.callback_query(F.data.startswith("flat_new_"))
async def handle_flat_new(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[-1])
    user_mode[user_id] = "flat_lay_format"
    flat_lay_active[user_id] = False
    balance = get_balance(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📐 Исходный формат", callback_data=f"flatfmt_original_{user_id}")],
        [InlineKeyboardButton(text="📱 1:1 (квадрат)", callback_data=f"flatfmt_1_1_{user_id}")],
        [InlineKeyboardButton(text="📱 4:5 (Instagram пост)", callback_data=f"flatfmt_4_5_{user_id}")],
        [InlineKeyboardButton(text="📱 9:16 (сториз)", callback_data=f"flatfmt_9_16_{user_id}")],
    ])
    await callback.answer()
    await callback.message.answer(
        f"📷 <b>Новый Flat Lay</b>\n\n"
        f"💎 Баланс: {balance}\n\n"
        f"Выбери формат:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ===== ДОРАБОТКА РЕЗУЛЬТАТА =====
@dp.callback_query(F.data.startswith("gen_refine_"))
async def handle_gen_refine(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    gen_type = parts[2]
    user_id = int(parts[3])
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Доработать результат</b>\n\n"
        "Каждая доработка тратит 1 генерацию.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Улучшить", callback_data=f"gen_go_ok_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_go_pose_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_go_retouch_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="📐 Только формат", callback_data=f"gen_go_format_only_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_{gen_type}_{user_id}")],
        ]))


# ===== УСИЛЕНИЕ =====
@dp.callback_query(F.data.startswith("gen_boost_back_"))
async def handle_gen_boost_back(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@dp.callback_query(F.data.startswith("gen_boost_menu_"))
async def handle_gen_boost_menu(callback: CallbackQuery):
    parts = callback.data.split("_")
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
            [InlineKeyboardButton(text="💡 Исправить свет", callback_data=f"gen_boost_light_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🧍 Исправить позу", callback_data=f"gen_boost_pose_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="💫 Ретушь", callback_data=f"gen_boost_retouch_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="✏️ Свой промпт", callback_data=f"gen_go_custom_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"gen_boost_back_{gen_type}_{user_id}")],
        ]))


@dp.callback_query(F.data.startswith("gen_boost_"))
async def handle_gen_boost(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    boost_type = parts[2]
    gen_type = parts[3]
    user_id = int(parts[4])

    analysis = last_analysis.get(user_id, {})
    what_is_wrong = analysis.get("what_is_wrong", "")
    how_to_fix = analysis.get("how_to_fix", "")

    # Общие правила — сохраняем идею, людей, лица, одежду
    base_rules = (
        "СОХРАНИ идею, сюжет, атмосферу. "
        "СОХРАНИ всех людей, их лица, причёски, аксессуары. "
        "Верхнюю одежду не меняй. "
        "Если дорисовываешь низ — современно: "
        "брюки прямые, свободные, широкие джинсы, чиносы. "
        "Платье прямого силуэта, миди. "
        "Обувь по контексту. "
        "Фигуру сохрани как на фото. "
        "НЕ добавляй новых людей, животных, предметов. "
        "НЕ убирай существующие объекты. "
    )
    analysis_block = ""
    if what_is_wrong and what_is_wrong != "---":
        analysis_block += f"КОНКРЕТНАЯ ОШИБКА КАДРА: {what_is_wrong}. "
    if how_to_fix and how_to_fix != "---":
        analysis_block += f"КАК ИСПРАВИТЬ: {how_to_fix}. "

    if boost_type == "horizon":
        wish = (
            f"{base_rules}"
            f"САМОЕ ГЛАВНОЕ: выровняй горизонт до идеально ровного. "
            f"{analysis_block}"
            f"Не трогай остальное — только горизонт. "
        )
    elif boost_type == "clean":
        wish = (
            f"{base_rules}"
            f"Убери ВЕСЬ мусор с фона: случайные предметы, провода, урны, прохожих. "
            f"Сделай фон чистым и аккуратным. "
            f"{analysis_block}"
        )
    elif boost_type == "light":
        wish = (
            f"{base_rules}"
            f"Полностью переработай освещение: убери пересветы, вытяни тени, "
            f"сделай свет мягче, объёмнее и естественнее. "
            f"{analysis_block}"
        )
    elif boost_type == "pose":
        wish = (
            f"{base_rules}"
            f"Сделай позу человека значительно естественнее и изящнее. "
            f"Исправь зажатость, положение рук и корпуса. "
            f"НЕ меняй лицо и верхнюю одежду. "
            f"Если дорисовываешь низ — современно. "
            f"{analysis_block}"
        )
    elif boost_type == "retouch":
        wish = (
            f"{base_rules}"
            f"Сделай ЗАМЕТНУЮ ПРОФЕССИОНАЛЬНУЮ РЕТУШЬ ПОРТРЕТА. "
            f"Изменения должны быть ВИДНЫ сразу, а не едва уловимы. "
            f"ЛИЦО: сгладь ВСЕ морщины и складки — лоб, носогубные, вокруг глаз. "
            f"Убери тёмные круги и мешки под глазами ЗАМЕТНО. "
            f"Выровняй тон кожи: убери покраснения, пигментные пятна, неровности. "
            f"Смягчи резкие тени на лице. "
            f"ГЛАЗА: осветли белки, убери красноту, сделай взгляд ярче, добавь блик. "
            f"ВОЛОСЫ: убери выбившиеся волоски, сделай причёску аккуратной. "
            f"ГУБЫ: сделай их чуть более выразительными, но естественными. "
            f"СОХРАНИ черты лица, форму носа, губ, разрез глаз — не меняй человека. "
            f"Кожа должна остаться естественной, с лёгкой текстурой, без «пластика». "
            f"НЕ трогай фон, одежду, позу, свет, композицию. "
            f"{analysis_block}"
        )
    elif boost_type == "full":
        wish = (
            f"{base_rules}"
            f"Полностью переработай кадр: композицию, позу, фон, свет. "
            f"Сделай его значительно красивее и гармоничнее. "
            f"Выстрой композицию по правилу третей, добавь воздуха, "
            f"улучши свет, убери лишнее с фона. "
            f"Сохрани сюжет и всех людей. "
            f"{analysis_block}"
            f"Изменения должны быть ОЧЕНЬ заметными. "
        )
    else:
        wish = (
            f"{base_rules}"
            f"Улучши фото значительно. "
            f"{analysis_block}"
        )

    gen_wish[user_id] = wish
    gen_used_count[user_id] = 0
    await callback.answer("⚡ Усиливаю...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False, use_original=True, mode="boost")


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
    saved_wish = last_prompt.get(user_id, "")
    saved_fmt = last_format.get(user_id, "")
    if saved_wish:
        gen_wish[user_id] = saved_wish
    if saved_fmt:
        gen_format[user_id] = saved_fmt
    old_photo = last_photo.get(user_id)
    await callback.answer("🔄 Генерирую другой вариант...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False, mode="retry")
    new_photo = last_photo.get(user_id)
    if new_photo != old_photo:
        gen_retry_count[user_id] = 1


# ===== ОБРАБОТКА ФОТО =====
@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")
    logger.info(f"📸 handle_photo: user={user_id}, mode={mode}, xmas_awaiting={user_id in xmas_awaiting_photo}")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"
    image = download_and_resize(photo_url, target_width=1024)
    image_bytes = image_to_bytes(image)

    if user_id in xmas_awaiting_photo:
        await handle_xmas_photo(message, user_id, image_bytes)
        return
    if is_user_in_xmas_flow(user_id):
        await message.answer(
            "⚠️ Вы ещё не завершили настройку фотосессии.\n\n"
            "Вернитесь назад и выберите все параметры до конца, "
            "а потом нажмите «📸 Загрузить фото»."
        )
        return

    if is_user_in_ref_flow(user_id):
        handled = await handle_reference_photo(message, user_id, image_bytes)
        if handled:
            return

    if user_id in holiday_awaiting_photo:
        await handle_holiday_photo(message, user_id, image_bytes)
        return

    if user_id in wedding_awaiting_photo:
        await handle_wedding_photo(message, user_id, image_bytes)
        return

    if user_id in prompt_awaiting_photo:
        handled = await handle_prompt_photo(message, user_id, image_bytes)
        if handled:
            return

    last_photo[user_id] = image_bytes
    original_photo[user_id] = image_bytes
    gen_retry_count[user_id] = 0
    gen_used_count[user_id] = 0
    last_prompt[user_id] = ""
    last_format[user_id] = ""
    gen_fail_count[user_id] = 0
    gen_fail_time[user_id] = None

    if mode in ("gen_wish_free", "gen_wish_paid"):
        await do_generation(user_id, message.chat.id, "paid")
        user_mode[user_id] = "free"
        return

    if mode == "flat_custom":
        gen_wish[user_id] = message.text if hasattr(message, 'text') else ""
        await do_generation(user_id, message.chat.id, "paid", check_diff=False)
        user_mode[user_id] = "free"
        return

    if mode == "change_format":
        await message.answer("Выбери формат:", reply_markup=format_keyboard("paid"))
        return

    if mode == "change_format_only":
        await message.answer(
            "📐 <b>Смена формата</b>\n\nВыбери формат:",
            parse_mode="HTML",
            reply_markup=format_keyboard("paid")
        )
        return

    if mode == "style_photo":
        keyboard = []
        for i in range(0, len(MAIN_STYLES), 2):
            row = []
            for style in MAIN_STYLES[i:i+2]:
                row.append(InlineKeyboardButton(
                    text=ALL_STYLES[style],
                    callback_data=f"gen_style_{style}_paid_{user_id}"
                ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(text="✨ Ещё стили...", callback_data=f"gen_style_more_paid_{user_id}")])
        await message.answer(
            "🎨 <b>Выбери стиль:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        return

    if mode == "studio_angle":
        user_mode[user_id] = "studio_bg"
        await message.answer(
            "🧑💼 <b>Выберите ракурс:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Анфас", callback_data="angle_front")],
                [InlineKeyboardButton(text="Полуоборот", callback_data="angle_half")],
            ])
        )
        return

    if mode.startswith("doc_photo_"):
        doc_type = mode.replace("doc_photo_", "")
        user_mode[user_id] = f"doc_outfit_{doc_type}"
        await message.answer(
            "👔 <b>Выберите категорию костюма:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👔 Обычные костюмы", callback_data=f"outfitcat_regular_{doc_type}")],
                [InlineKeyboardButton(text="🎖 Специализированные", callback_data=f"outfitcat_special_{doc_type}")],
                [InlineKeyboardButton(text="👕 Оставить свою одежду", callback_data=f"outfitcat_original_{doc_type}")],
            ])
        )
        return

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

    if mode == "interior_photo":
        aligned = align_interior(image)
        aligned_bytes = image_to_bytes(aligned)
        last_photo[user_id] = aligned_bytes
        original_photo[user_id] = image_bytes
        await message.answer_photo(
            BufferedInputFile(aligned_bytes, filename="aligned.jpg"),
            caption="✨ Выбери, какой свет должен быть на фото:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☀️ Дневной свет (лампы выключены)", callback_data=f"int_setlight_natural_{user_id}")],
                [InlineKeyboardButton(text="💡 С лампами (светильники включены)", callback_data=f"int_setlight_lights_{user_id}")],
                [InlineKeyboardButton(text="🔄 Как на фото (не менять)", callback_data=f"int_setlight_keep_{user_id}")],
            ])
        )
        return

    if mode in (
        "flat_lay_format", "doc_type", "studio_format",
        "studio_portrait_generating", "studio_bg", "studio_outfit",
        "studio_hair", "flat_custom_prompt",
    ) or mode.startswith(("doc_outfit_", "doc_hair_", "int_setlight_")):
        await message.answer(
            "⚠️ Сначала закончи настройку — выбери параметр из меню выше, потом пришли фото.",
            parse_mode="HTML"
        )
        return

    # ===== АНАЛИЗ ФОТО =====
    if not (user_id == 456504792 and test_mode):
        can, left = _analysis_check_and_get(user_id)
        if not can:
            await message.answer(
                "🔍 <b>Лимит анализов исчерпан.</b>\n\n"
                "Бесплатные обновляются каждый день — 5 штук.\n\n"
                "Хочешь больше сейчас? Купи пакет:\n"
                "Платные анализы <b>не сгорают</b> — тратятся только тогда, "
                "когда заканчивается бесплатный лимит.",
                parse_mode="HTML",
                reply_markup=buy_analyses_keyboard()
            )
            return

    processing_msg = await message.answer("🔍 Анализирую кадр...")

    try:
        course_topic = None
        effective_has_access = has_access(user_id)
        if effective_has_access and user_mode.get(user_id) == "course":
            from course import get_current_topic
            course_topic = get_current_topic(user_id)

        result = analyze_photo(image_bytes, course_topic=course_topic)

        if result is not None:
            error_type = result.get("error_type", "unknown")
            last_analysis[user_id] = result
            add_analysis(user_id, error_type)
            _add_history(user_id, "analysis", f"Ошибки: {error_type}")
            _analysis_increment(user_id)

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

        if not (user_id == 456504792 and test_mode):
            free_left = _analysis_get_free_left(user_id)
            paid_left = paid_analyses.get(user_id, 0)
            if free_left > 0:
                await message.answer(
                    f"🔍 Осталось бесплатных анализов сегодня: {free_left} из {FREE_ANALYSIS_PER_DAY}"
                )
            elif paid_left > 0:
                await message.answer(
                    f"🔍 Бесплатные закончились. Платных в запасе: {paid_left}"
                )

        # Проверка задания курса
        if has_access(user_id) and user_mode.get(user_id) == "course":
            status = get_status(user_id)
            if status is not None and "День" in status:
                add_photo(user_id)
                check_text = check_day(user_id, result)
                if check_text:
                    if _is_trial(user_id) and "задание выполнено" in check_text.lower():
                        link = create_payment_link(490, "Оплата за мини-курс", user_id) or "https://t.me/moy_razbor_bot"
                        check_text += (
                            "\n\n🎉 Пробный день пройден!\n"
                            "💳 Оплати 490 ₽ и продолжай!"
                        )
                        await message.answer(check_text, parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Оплатить 490 ₽", url=link)]
                            ]))
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


# ===== ОБРАБОТКА ДОКУМЕНТОВ (костюмы, причёски) =====
@dp.callback_query(F.data.startswith("outfitcat_"))
async def handle_outfitcat(callback: CallbackQuery):
    parts = callback.data.split("_")
    category = parts[1]
    doc_type = parts[2]
    user_id = callback.from_user.id
    await callback.answer()
    if category == "regular":
        user_mode[user_id] = f"doc_outfit_regular_{doc_type}"
        await callback.message.answer(
            "👔 <b>Выберите костюм:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пиджак с галстуком", callback_data=f"outfit_jacket_tie_{doc_type}")],
                [InlineKeyboardButton(text="Пиджак без галстука", callback_data=f"outfit_jacket_{doc_type}")],
                [InlineKeyboardButton(text="Голубая рубашка", callback_data=f"outfit_blue_shirt_{doc_type}")],
                [InlineKeyboardButton(text="Белая рубашка", callback_data=f"outfit_shirt_{doc_type}")],
                [InlineKeyboardButton(text="Белая футболка", callback_data=f"outfit_tshirt_{doc_type}")],
                [InlineKeyboardButton(text="Тёмная рубашка", callback_data=f"outfit_dark_shirt_{doc_type}")],
                [InlineKeyboardButton(text="Блузка (женская)", callback_data=f"outfit_blouse_{doc_type}")],
                [InlineKeyboardButton(text="Тёмная водолазка", callback_data=f"outfit_turtleneck_{doc_type}")],
            ])
        )
    elif category == "special":
        user_mode[user_id] = f"doc_outfit_special_{doc_type}"
        await callback.message.answer(
            "🎖 <b>Выберите специализированный костюм:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🪖 Военный", callback_data=f"outfit_military_{doc_type}")],
                [InlineKeyboardButton(text="🚆 РЖД", callback_data=f"outfit_rzd_{doc_type}")],
                [InlineKeyboardButton(text="👮 Полиция", callback_data=f"outfit_police_{doc_type}")],
            ])
        )
    elif category == "original":
        user_mode[user_id] = f"doc_hair_original_{doc_type}"
        await callback.message.answer(
            "💇 <b>Выберите причёску:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оставить как есть", callback_data=f"hair_keep_{doc_type}")],
                [InlineKeyboardButton(text="Аккуратная укладка", callback_data=f"hair_neat_{doc_type}")],
                [InlineKeyboardButton(text="Лёгкая коррекция", callback_data=f"hair_fix_{doc_type}")],
            ])
        )


@dp.callback_query(F.data.startswith("outfit_"))
async def handle_outfit(callback: CallbackQuery):
    raw = callback.data.replace("outfit_", "")
    if raw.endswith("_passport"):
        outfit = raw[:-len("_passport")]
        doc_type = "passport"
    elif raw.endswith("_3x4"):
        outfit = raw[:-len("_3x4")]
        doc_type = "3x4"
    else:
        outfit = raw
        doc_type = "passport"
    user_id = callback.from_user.id
    await callback.answer()
    user_mode[user_id] = f"doc_hair_{outfit}_{doc_type}"
    await callback.message.answer(
        "💇 <b>Выберите причёску:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оставить как есть", callback_data=f"hair_keep_{outfit}_{doc_type}")],
            [InlineKeyboardButton(text="Аккуратная укладка", callback_data=f"hair_neat_{outfit}_{doc_type}")],
            [InlineKeyboardButton(text="Лёгкая коррекция", callback_data=f"hair_fix_{outfit}_{doc_type}")],
        ])
    )


@dp.callback_query(F.data.startswith("hair_") & ~F.data.startswith("studio_hair_"))
async def handle_hair(callback: CallbackQuery):
    raw = callback.data.replace("hair_", "")
    if raw.endswith("_passport"):
        body = raw[:-len("_passport")]
        doc_type = "passport"
    elif raw.endswith("_3x4"):
        body = raw[:-len("_3x4")]
        doc_type = "3x4"
    else:
        body = raw
        doc_type = "passport"

    first_underscore = body.find("_")
    if first_underscore == -1:
        hair = body
        outfit = "original"
    else:
        hair = body[:first_underscore]
        outfit = body[first_underscore + 1:]
    user_id = callback.from_user.id
    await callback.answer()
    outfit_names = {
        "jacket_tie": "строгий пиджак с завязанным галстуком",
        "jacket": "пиджак без галстука",
        "blue_shirt": "голубая рубашка",
        "shirt": "белая рубашка",
        "tshirt": "белая футболка",
        "dark_shirt": "тёмная рубашка",
        "blouse": "светлая блузка",
        "turtleneck": "тёмная водолазка",
        "original": "оставить свою одежду с фото",
        "military": "военная форма",
        "rzd": "форма РЖД",
        "police": "полицейская форма",
    }
    outfit_name = outfit_names.get(outfit, outfit)
    hair_names = {
        "keep": "оставить причёску как есть",
        "neat": "аккуратная укладка",
        "fix": "лёгкая коррекция причёски",
    }
    hair_name = hair_names.get(hair, hair)
    prompt = (
        f"Сделай деловой портрет для документов. Белый фон. Лицо анфас, плечи видны. "
        f"Нейтральное выражение. "
        f"ОДЕЖДА: {outfit_name}. "
        f"СТРОГО ТОЛЬКО ЭТА ОДЕЖДА — не добавляй пиджак, галстук, бабочку, жилет, "
        f"если они не указаны выше. "
        f"Если указана рубашка — только рубашка, без пиджака и галстука. "
        f"Если указана футболка — только футболка. "
        f"Если указана водолазка — только водолазка. "
        f"НЕ дорисовывай никаких лишних предметов одежды. "
        f"Причёска: {hair_name}. "
        f"Студийный свет. Сохрани черты лица. Не меняй лицо."
    )
    gen_wish[user_id] = prompt
    if doc_type == "3x4":
        gen_format[user_id] = "3x4"
    else:
        gen_format[user_id] = "passport"
    flat_lay_active[user_id] = False
    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False)


@dp.callback_query(F.data.startswith("doc_next_"))
async def handle_doc_next(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    await callback.answer()
    user_mode[user_id] = "doc_type"
    await callback.message.answer(
        "Выберите тип документа:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Паспорт РФ (35×45 мм)", callback_data="doctype_passport")],
            [InlineKeyboardButton(text="📇 Документы (30×40 мм)", callback_data="doctype_3x4")],
        ])
    )


@dp.callback_query(F.data.startswith("doc_retry_"))
async def handle_doc_retry(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    if gen_retry_count.get(user_id, 0) >= 1:
        await callback.answer("Лимит перегенераций исчерпан.", show_alert=True)
        return
    saved_wish = last_prompt.get(user_id, "")
    saved_fmt = last_format.get(user_id, "")
    if saved_wish:
        gen_wish[user_id] = saved_wish
    if saved_fmt:
        gen_format[user_id] = saved_fmt
    old_photo = last_photo.get(user_id)
    await callback.answer("🔄 Генерирую новый вариант...")
    await do_generation(user_id, callback.message.chat.id, "paid", check_diff=False, mode="retry")
    new_photo = last_photo.get(user_id)
    if new_photo != old_photo:
        gen_retry_count[user_id] = 1


# ===== СТИЛИЗАЦИЯ =====
ALL_STYLES = {
    "film": "🎞️ Плёнка",
    "retro80": "🌈 Ретро 80-х",
    "painting": "🖼️ Картина",
    "anime": "🎌 Аниме",
    "comics": "💥 Комикс",
    "aquarel": "🎨 Акварель",
    "steampunk": "⚙️ Стимпанк",
    "vintage": "📜 Старинная",
    "gothic": "🦇 Готика",
    "pastel": "🌸 Пастель",
    "cinema": "🎬 Кино",
    "pencil": "✏️ Карандаш",
    "polaroid": "📷 Полароид",
    "funny": "😹 Ржака-портрет",
}

MAIN_STYLES = ["film", "retro80", "painting", "anime", "comics", "aquarel"]

STYLE_PROMPTS = {
    "film": (
        "Сделай фото в стиле плёночной фотографии. "
        "Добавь зернистость, лёгкий винтажный оттенок, "
        "мягкие тёплые тона, как у плёнки Kodak. "
        "НЕ меняй сюжет, людей и композицию."
    ),
    "retro80": (
        "Сделай фото в эстетике ретро 80-х: "
        "неоновые акценты, синтвейв-палитра (розовый, голубой, фиолетовый), "
        "яркие контрастные цвета, лёгкое свечение. "
        "НЕ меняй сюжет, людей и композицию."
    ),
    "painting": (
        "Преврати фото в живописную картину маслом. "
        "Видимые мазки кисти, насыщенные цвета, художественная текстура. "
        "Стиль как у классической живописи. "
        "Сохрани всех людей и композицию, но в виде картины."
    ),
    "anime": (
        "Преврати фото в кадр из японского аниме. "
        "Стиль студии Ghibli или Makoto Shinkai: "
        "чистые линии, яркие цвета, большие выразительные глаза, "
        "детализированный фон, мягкий свет. "
        "Все люди с фото должны быть УЗНАВАЕМЫ в аниме-стиле."
    ),
    "comics": (
        "Преврати фото в яркий рисованный комикс. "
        "3 панели с одной историей на одной картинке. "
        "Чёрные жирные контуры, плоские яркие цвета, "
        "штриховка, динамика. "
        "В каждой панели — короткая надпись на РУССКОМ языке. "
        "СОХРАНИ всех людей с фото — никого не убирай и не добавляй. "
        "ЖЁСТКОЕ ПРАВИЛО ПО ОДЕЖДЕ И ВНЕШНОСТИ: "
        "НА ВСЕХ 3 ПАНЕЛЯХ у каждого персонажа должна быть ОДНА И ТА ЖЕ ОДЕЖДА — "
        "та же, что на исходном фото: тот же цвет, фасон, детали. "
        "НЕ придумывай новую одежду — сохрани ту, что есть на фото. "
        "НЕ меняй одежду, причёску, цвет волос, аксессуары между панелями. "
        "Все персонажи должны выглядеть ОДИНАКОВО на всех панелях — "
        "меняется только поза и ракурс, но НЕ внешность и НЕ одежда."
    ),
    "aquarel": (
        "Преврати фото в нежную акварельную живопись. "
        "Прозрачные слои краски, мягкие переходы, "
        "светлые тона, лёгкость и воздушность. "
        "Сохрани всех людей и композицию."
    ),
    "steampunk": (
        "Стилизуй фото под стимпанк: "
        "паровая эстетика, латунь, медь, шестерёнки, "
        "тёплые коричнево-золотые тона, викторианские детали. "
        "Люди выглядят как в мире стимпанка, но узнаваемы. "
        "НЕ добавляй новых людей."
    ),
    "vintage": (
        "Сделай фото как старинный архивный снимок XIX века. "
        "Сепия или приглушённые коричневатые тона, "
        "лёгкие трещинки и потёртости по краям, "
        "мягкий фокус, виньетка, ощущение старости. "
        "НЕ меняй людей и композицию."
    ),
    "gothic": (
        "Сделай фото в готической эстетике. "
        "Мрачные тона, глубокие тени, "
        "тёмная романтичная атмосфера, "
        "лёгкий туман, драматичный свет. "
        "Сохрани всех людей и сюжет."
    ),
    "pastel": (
        "Добавь нежные пастельные тона. "
        "Мягкие, светлые оттенки, "
        "воздушная атмосфера, лёгкость. "
        "НЕ меняй людей и композицию."
    ),
    "cinema": (
        "Сделай фото кинематографичным кадром. "
        "Глубокие цвета, контрастный свет, "
        "широкоэкранная композиция, "
        "стиль как из художественного фильма. "
        "Сохрани всех людей и сюжет."
    ),
    "pencil": (
        "Преврати фото в рисунок ЦВЕТНЫМИ карандашами. "
        "Как будто нарисовано на бумаге цветными карандашами: "
        "видны штрихи, текстура бумаги, "
        "мягкие переходы цвета, лёгкая небрежность. "
        "Все люди должны быть УЗНАВАЕМЫ. "
        "Сохрани всех людей и композицию."
    ),
    "polaroid": (
        "Сделай фото в стиле винтажного полароида. "
        "Характерная белая рамка с широким нижним полем, "
        "лёгкий винтажный оттенок, мягкий фокус, "
        "небольшая зернистость. "
        "НЕ меняй людей и композицию."
    ),
    "funny": (
        "Turn this photo into a doodle-style character that looks "
        "intentionally ugly and funny, similar to a child's crayon drawing. "
        "Use a rough black outline like crayon or pencil, "
        "with messy scribble coloring. "
        "Keep ALL people from the original photo — do not remove or add anyone. "
        "Faces and bodies simplified and exaggerated, but still recognizable. "
        "The result should look FUNNY and KIND, not scary. "
        "Background — simple, schematic, like a child's drawing. "
        "Vibrant child-like colors."
    ),
}

STYLE_DESCRIPTIONS = {
    "film": (
        "🎞️ <b>Плёнка</b>\n\n"
        "Что будет:\n"
        "• Зернистость, как у плёночной фотографии\n"
        "• Тёплые винтажные тона (стиль Kodak)\n"
        "• Мягкий фокус\n\n"
        "Сюжет, люди и композиция сохранятся."
    ),
    "retro80": (
        "🌈 <b>Ретро 80-х</b>\n\n"
        "Что будет:\n"
        "• Неоновые акценты и свечение\n"
        "• Синтвейв-палитра: розовый, голубой, фиолетовый\n"
        "• Яркий контраст, как в клипах 80-х\n\n"
        "Сюжет и люди сохранятся."
    ),
    "painting": (
        "🖼️ <b>Картина</b>\n\n"
        "Что будет:\n"
        "• Фото превратится в живопись маслом\n"
        "• Видимые мазки кисти, текстура\n"
        "• Насыщенные художественные цвета\n\n"
        "⚠️ Это художественная стилизация — фото станет картиной."
    ),
    "anime": (
        "🎌 <b>Аниме</b>\n\n"
        "Что будет:\n"
        "• Стиль японской анимации (Ghibli / Shinkai)\n"
        "• Чистые линии, яркие цвета\n"
        "• Большие выразительные глаза\n"
        "• Детализированный фон\n\n"
        "⚠️ Люди станут аниме-персонажами, но останутся узнаваемыми."
    ),
    "comics": (
        "💥 <b>Комикс</b>\n\n"
        "Что будет:\n"
        "• Фото превратится в рисованный комикс\n"
        "• 3 панели с одной историей\n"
        "• Чёрные жирные контуры, плоские цвета\n"
        "• Короткие надписи на русском в каждой панели\n\n"
        "⚠️ Все люди сохранятся, но станут нарисованными."
    ),
    "aquarel": (
        "🎨 <b>Акварель</b>\n\n"
        "Что будет:\n"
        "• Нежная акварельная живопись\n"
        "• Прозрачные слои, мягкие переходы\n"
        "• Светлые воздушные тона\n\n"
        "⚠️ Фото станет акварельным рисунком."
    ),
    "steampunk": (
        "⚙️ <b>Стимпанк</b>\n\n"
        "Что будет:\n"
        "• Паровая эстетика, латунь и медь\n"
        "• Шестерёнки, викторианские детали\n"
        "• Тёплые коричнево-золотые тона\n\n"
        "⚠️ Люди останутся узнаваемыми, но в мире стимпанка."
    ),
    "vintage": (
        "📜 <b>Старинная</b>\n\n"
        "Что будет:\n"
        "• Стиль архивного снимка XIX века\n"
        "• Сепия и приглушённые тона\n"
        "• Трещинки и потёртости по краям\n"
        "• Мягкий фокус, виньетка\n\n"
        "Сюжет и люди сохранятся."
    ),
    "gothic": (
        "🦇 <b>Готика</b>\n\n"
        "Что будет:\n"
        "• Мрачная тёмная эстетика\n"
        "• Глубокие тени, драматичный свет\n"
        "• Лёгкий туман, атмосфера тайны\n\n"
        "Сюжет и люди сохранятся."
    ),
    "pastel": (
        "🌸 <b>Пастель</b>\n\n"
        "Что будет:\n"
        "• Нежные светлые тона\n"
        "• Мягкие переходы цвета\n"
        "• Воздушная лёгкая атмосфера\n\n"
        "Сюжет и люди сохранятся."
    ),
    "cinema": (
        "🎬 <b>Кино</b>\n\n"
        "Что будет:\n"
        "• Кинематографичный кадр\n"
        "• Глубокие цвета, контрастный свет\n"
        "• Стиль как из художественного фильма\n\n"
        "Сюжет и люди сохранятся."
    ),
    "pencil": (
        "✏️ <b>Карандаш</b>\n\n"
        "Что будет:\n"
        "• Рисунок ЦВЕТНЫМИ карандашами\n"
        "• Видны штрихи, текстура бумаги\n"
        "• Мягкие переходы цвета, лёгкая небрежность\n\n"
        "⚠️ Люди останутся узнаваемыми, но фото станет рисунком."
    ),
    "polaroid": (
        "📷 <b>Полароид</b>\n\n"
        "Что будет:\n"
        "• Винтажный кадр Polaroid\n"
        "• Белая рамка с широким нижним полем\n"
        "• Мягкий фокус, лёгкая зернистость\n\n"
        "Сюжет и люди сохранятся."
    ),
    "funny": (
        "😹 <b>Ржака-портрет</b>\n\n"
        "Что будет:\n"
        "• Смешной детский рисунок (дудл)\n"
        "• Намеренно неуклюжий, как у ребёнка\n"
        "• Грубые контуры, раскраска каракулями\n"
        "• Утрированные, но узнаваемые лица\n\n"
        "⚠️ Это шуточная стилизация. Будет ЗАБАВНО и по-доброму."
    ),
}


@dp.callback_query(F.data.startswith("gen_style_menu_full_"))
async def handle_gen_style_menu_full(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[4]
    user_id = int(parts[5])
    await callback.answer()
    keyboard = []
    for i in range(0, len(MAIN_STYLES), 2):
        row = []
        for style in MAIN_STYLES[i:i+2]:
            row.append(InlineKeyboardButton(text=ALL_STYLES[style], callback_data=f"gen_style_{style}_{gen_type}_{user_id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="✨ Ещё стили...", callback_data=f"gen_style_more_{gen_type}_{user_id}")])
    keyboard.append([InlineKeyboardButton(text="✏️ Свой стиль", callback_data=f"gen_style_custom_{gen_type}_{user_id}")])
    await callback.message.answer("🎨 <b>Выбери стиль:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@dp.callback_query(F.data.startswith("gen_style_more_"))
async def handle_gen_style_more(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    all_keys = list(ALL_STYLES.keys())
    keyboard = []
    for i in range(0, len(all_keys), 2):
        row = []
        for style in all_keys[i:i+2]:
            row.append(InlineKeyboardButton(text=ALL_STYLES[style], callback_data=f"gen_style_{style}_{gen_type}_{user_id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="✏️ Свой стиль", callback_data=f"gen_style_custom_{gen_type}_{user_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"gen_style_menu_full_{gen_type}_{user_id}")])
    await callback.message.answer("🎨 <b>Все стили:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@dp.callback_query(F.data.startswith("gen_style_custom_"))
async def handle_gen_style_custom(callback: CallbackQuery):
    parts = callback.data.split("_")
    gen_type = parts[3]
    user_id = int(parts[4])
    await callback.answer()
    user_mode[user_id] = f"custom_style_{gen_type}"
    await callback.message.answer(
        "✏️ <b>Свой стиль</b>\n\n"
        "Опиши, какой стиль хочешь. Например:\n"
        "• «как в фильме Wes Anderson»\n"
        "• «стиль Тим Бёртон»\n"
        "• «зимняя сказка»\n"
        "• «обложка Vogue»\n"
        "• «как картина Ван Гога»\n\n"
        "Напиши свой вариант одним сообщением.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("gen_style_"))
async def handle_gen_style(callback: CallbackQuery):
    if "menu" in callback.data or "more" in callback.data:
        return
    parts = callback.data.split("_")
    if len(parts) != 5:
        await callback.answer("Ошибка данных")
        return
    style = parts[2]
    gen_type = parts[3]
    if style not in ALL_STYLES:
        await callback.answer("Неизвестный стиль")
        return
    try:
        user_id = int(parts[4])
    except ValueError:
        await callback.answer("Ошибка данных")
        return

    await callback.answer()
    description = STYLE_DESCRIPTIONS.get(style, f"🎨 <b>{ALL_STYLES[style]}</b>\n\nСтилизация будет применена к фото.")
    await callback.message.answer(
        f"{description}\n\n"
        f"⚠️ <b>Важно:</b> ИИ не всегда точно передаёт замысел. "
        f"Результат — художественная интерпретация. "
        f"Если что-то не понравится — 1 бесплатная перегенерация.\n\n"
        f"💰 Стоимость: 1 генерация",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Стилизовать", callback_data=f"confirm_style_{style}_{gen_type}_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ])
    )


@dp.callback_query(F.data.startswith("confirm_style_"))
async def handle_confirm_style(callback: CallbackQuery):
    parts = callback.data.split("_")
    style = parts[2]
    gen_type = parts[3]
    user_id = int(parts[4])
    if style not in ALL_STYLES:
        await callback.answer("Неизвестный стиль")
        return
    gen_wish[user_id] = STYLE_PROMPTS.get(style, "Примени художественный стиль.")
    user_mode[user_id] = f"gen_wish_{gen_type}"
    gen_format[user_id] = "original"
    style_active[user_id] = True
    await callback.answer("🎨 Применяю стиль...")
    await do_generation(user_id, callback.message.chat.id, gen_type, check_diff=False)
    user_mode[user_id] = "free"


# ===== ЛОГИКА КУРСА =====
def _is_trial(user_id: int) -> bool:
    users = _load_users()
    for key, data in users.items():
        if isinstance(data, dict) and data.get("username") == str(user_id):
            return data.get("trial", False)
    return False


async def handle_course_status_logic(user_id: int, chat_id: int):
    effective = has_access(user_id)
    if effective:
        user_mode[user_id] = "course"
        status = get_status(user_id)
        if status:
            if "День 0" in status or "Подготовка" in status:
                await bot.send_message(chat_id, status, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")]
                    ]))
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
            [InlineKeyboardButton(text="💳 Оплатить (490 ₽)", callback_data="pay_course")]
        ]))


@dp.callback_query(F.data == "start_trial")
async def handle_start_trial(callback: CallbackQuery):
    await callback.answer()
    activate_free_trial(callback.from_user.id)
    user_mode[callback.from_user.id] = "course"
    status = get_status(callback.from_user.id)
    if status:
        await callback.message.answer(status, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")]
            ]))
        await send_photos(callback.message.chat.id, 0)


@dp.callback_query(F.data == "pay_course")
async def handle_pay_course(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(490, "Оплата за мини-курс", callback.from_user.id) or "https://t.me/moy_razbor_bot"
    await callback.message.answer(
        "💳 <b>Оплата курса — 490 ₽</b>\n\n"
        "Если Chrome не открывает страницу — используйте Яндекс Браузер.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 490 ₽", url=link)]
        ]))


@dp.callback_query(F.data == "course_status")
async def handle_course_status(callback: CallbackQuery):
    await callback.answer()
    await handle_course_status_logic(callback.from_user.id, callback.message.chat.id)


@dp.callback_query(F.data == "start_course_btn")
async def handle_start_course_btn(callback: CallbackQuery):
    await callback.answer("Кнопка нажата")
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
@dp.callback_query(F.data == "admin_menu_stats")
async def admin_menu_stats(callback: CallbackQuery):
    if callback.from_user.id != 456504792:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.answer()
    stats_data = load_stats_data()
    total_users = len(stats_data)
    total_analyses = sum(d.get("total", 0) for d in stats_data.values())
    await callback.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👤 Пользователей: {total_users}\n"
        f"📸 Анализов: {total_analyses}",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin_menu_users")
async def admin_menu_users(callback: CallbackQuery):
    if callback.from_user.id != 456504792:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.answer()
    stats_data = load_stats_data()
    text = "👤 <b>Пользователи:</b>\n\n"
    for uid, data in sorted(stats_data.items(), key=lambda x: x[1].get("total", 0), reverse=True):
        text += f"• <code>{uid}</code> — {data.get('total', 0)} анализов\n"
    await callback.message.answer(text or "Нет пользователей", parse_mode="HTML")


@dp.callback_query(F.data == "admin_menu_gen")
async def admin_menu_gen(callback: CallbackQuery):
    if callback.from_user.id != 456504792:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await callback.answer()
    text = "💎 <b>Генерации:</b>\n\n"
    for uid, c in paid_generations.items():
        if c > 0:
            text += f"• <code>{uid}</code>: {c} шт\n"
    await callback.message.answer(text or "Нет оплаченных генераций", parse_mode="HTML")


@dp.callback_query(F.data == "promo_menu_create")
async def promo_menu_create(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "promo_create_name"
    await callback.message.answer(
        "➕ <b>Создание промокода</b>\n\n"
        "Введи название (латиницей):",
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
            "/admin stats — статистика\n"
            "/admin users — пользователи\n"
            "/admin gen — генерации\n"
            "/admin course — курс\n"
            "/admin orders — заказы",
            parse_mode="HTML")
        return
    command = args[1].lower()
    if command == "stats":
        stats_data = load_stats_data()
        total_users = len(stats_data)
        total_analyses = sum(d.get("total", 0) for d in stats_data.values())
        await message.answer(
            f"📊 <b>Статистика</b>\n\n👤 Пользователей: {total_users}\n📸 Анализов: {total_analyses}",
            parse_mode="HTML")
    elif command == "users":
        stats_data = load_stats_data()
        text = "👤 <b>Пользователи:</b>\n\n"
        for uid, data in sorted(stats_data.items(), key=lambda x: x[1].get("total", 0), reverse=True):
            text += f"• <code>{uid}</code> — {data.get('total', 0)} анализов\n"
        await message.answer(text or "Нет пользователей", parse_mode="HTML")
    elif command == "gen":
        text = "💎 <b>Генерации:</b>\n\n"
        for uid, c in paid_generations.items():
            if c > 0:
                text += f"• <code>{uid}</code>: {c} шт\n"
        await message.answer(text or "Нет оплаченных генераций", parse_mode="HTML")
    elif command == "orders":
        orders = _load_author_orders()
        if not orders:
            await message.answer("📭 Нет заказов")
            return
        text = "📸 <b>Заказы:</b>\n\n"
        for i, o in enumerate(orders):
            s = "✅" if o["status"] == "ready" else ("⏳" if o["status"] == "paid" else "✔️")
            text += f"#{i} | <code>{o['user_id']}</code> | Фото: {len(o.get('photos',[]))} | {s}\n"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Неизвестная команда")


# ===== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =====
@dp.message(~F.photo)
async def handle_non_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")
    text = message.text

    if await handle_xmas_custom_text(message, user_id, text):
        return

    if await handle_holiday_custom_text(message, user_id, text):
        return

    if await handle_wedding_custom_text(message, user_id, text):
        return
    
    if await handle_prompt_text(message, user_id, text):
        return

    if text in ("🛠 Инструменты", "📸 Разобрать фото", "🏠 Главное меню",
                "🎓 Мини-курс", "🎯 Авторский разбор", "💎 Баланс",
                "💛 Поддержать проект", "👤 Об авторе", "🎉 Праздники",
                "🔮 Карта дня"):
        _reset_all_flows(user_id)

    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_wish[user_id] = text
        await do_generation(user_id, message.chat.id, "paid")
        user_mode[user_id] = "free"
        return

    if mode.startswith("custom_style_"):
        gen_type = mode.replace("custom_style_", "")
        style_text = text.strip()[:500]
        if not style_text:
            await message.answer("✏️ Пусто. Опиши стиль словами.")
            return
        gen_wish[user_id] = (
            f"Примени художественный стиль: {style_text}. "
            f"СОХРАНИ всех людей с исходного фото, их лица, причёски и одежду. "
            f"НЕ добавляй новых людей и объектов. "
            f"Сюжет и композиция должны сохраниться. "
            f"Сделай стилизацию ЗАМЕТНОЙ и выразительной."
        )
        user_mode[user_id] = f"gen_wish_{gen_type}"
        gen_format[user_id] = "original"
        style_active[user_id] = True
        await do_generation(user_id, message.chat.id, gen_type, check_diff=False)
        user_mode[user_id] = "free"
        return

    if mode in ("flat_custom", "flat_custom_prompt"):
        gen_wish[user_id] = text
        flat_lay_active[user_id] = True
        await do_generation(user_id, message.chat.id, "paid", check_diff=False)
        user_mode[user_id] = "free"
        return

    if text == "🎫 Промо":
        await message.answer(
            "🎫 <b>Промокоды</b>\n\n"
            "Управление промокодами:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать", callback_data="promo_menu_create")],
                [InlineKeyboardButton(text="📋 Список", callback_data="promo_menu_list")],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data="promo_menu_delete")],
                [InlineKeyboardButton(text="🔄 Сбросить", callback_data="promo_menu_reset")],
            ])
        )
        await message.answer(
            "📖 <b>Примеры промокодов</b>\n\n"
            "<b>1. Обычный пакет генераций</b>\n"
            "Название: <code>WELCOME10</code>\n"
            "Количество: <code>10</code>\n"
            "Введите: <code>WELCOME10</code>\n"
            "→ даёт 10 генераций пользователю\n\n"
            "<b>2. Пробный пакет</b>\n"
            "Название: <code>TRIAL5</code>\n"
            "Количество: <code>5</code>\n"
            "Введите: <code>TRIAL5</code>\n"
            "→ даёт 5 генераций пользователю\n\n"
            "<b>3. Большой пакет на праздники</b>\n"
            "Название: <code>NY30</code>\n"
            "Количество: <code>30</code>\n"
            "Введите: <code>NY30</code>\n"
            "→ даёт 30 генераций пользователю\n\n"
            "<b>4. Доступ к мини-курсу</b>\n"
            "Название: <code>COURSEFREE</code>\n"
            "Количество: <code>course</code>\n"
            "Введите: <code>COURSEFREE course</code>\n"
            "→ открывает мини-курс полностью\n\n"
            "<b>Как создать:</b>\n"
            "1. Нажми «➕ Создать» → введи название\n"
            "2. Введи количество (число) или слово <code>course</code>\n"
            "3. Промокод готов — отправь его пользователям\n\n"
            "<b>Как активировать (со стороны пользователя):</b>\n"
            "Пользователь пишет: <code>/promo КОД</code>\n"
            "Например: <code>/promo WELCOME10</code>",
            parse_mode="HTML"
        )
        return

    if text == "📸 Заказы":
        orders = _load_author_orders()
        if not orders:
            await message.answer("📭 Нет заказов")
            return
        text_out = "📸 <b>Заказы:</b>\n\n"
        for i, o in enumerate(orders):
            s = "✅" if o["status"] == "ready" else ("⏳" if o["status"] == "paid" else "✔️")
            text_out += f"#{i} | <code>{o['user_id']}</code> | Фото: {len(o.get('photos',[]))} | {s}\n"
        await message.answer(text_out, parse_mode="HTML")
        return

    if text == "📊 Админка":
        await message.answer("📊 <b>Админ-панель</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_menu_stats")],
                [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin_menu_users")],
                [InlineKeyboardButton(text="💎 Генерации", callback_data="admin_menu_gen")],
            ]))
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
    if text == "🛠 Инструменты":
        balance = get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)
        await message.answer(
            f"🛠 <b>Инструменты</b>\n\n"
            f"💎 Твой баланс: {balance_text}\n\n"
            "Выбери инструмент:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✂️ Редактор", callback_data="change_format")],
                [InlineKeyboardButton(text="📷 Flat Lay", callback_data="flat_lay")],
                [InlineKeyboardButton(text="🎨 Стилизация", callback_data="style_photo")],
                [InlineKeyboardButton(text="🖼️ По референсу (Pinterest)", callback_data="ref_style")],
                [InlineKeyboardButton(text="🎨 Создать изображение", callback_data="prompt_start")],
                [InlineKeyboardButton(text="📄 Фото на документы", callback_data="doc_photo")],
                [InlineKeyboardButton(text="🧑💼 Студийный портрет", callback_data="studio_portrait")],
            ])
        )
        return
    if text == "💛 Поддержать проект":
        await message.answer("💛 Выбери сумму:", reply_markup=donate_keyboard())
        return
    if text == "👤 Об авторе":
        await message.answer(
            "📸 <b>Евгений Севостьянов</b>\nФотограф, преподаватель.\n\n"
            "📷 Instagram: @sevosphoto\n💬 Telegram: @sevosphoto\n🌐 VK: @cevoc\n\n"
            "━━━━━━━━━━━━━━━\n"
            "ИП Севостьянов Евгений Александрович\n"
            "ИНН: 701741776350\n"
            "Оплата через банк Точка",
            parse_mode="HTML"
        )
        return
    if text == "💎 Баланс":
        balance = get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)
        free_analyses = _analysis_get_free_left(user_id)
        paid_analyses_left = paid_analyses.get(user_id, 0)
        free_text = "∞" if (user_id == 456504792 and test_mode) else str(free_analyses)
        await message.answer(
            f"💎 <b>Твой баланс</b>\n\n"
            f"⚡ <b>Генерации:</b> {balance_text}\n"
            f"1 генерация = 1 результат в любом инструменте.\n"
            f"В каждой — 1 бесплатная перегенерация.\n\n"
            f"🔍 <b>Анализы:</b>\n"
            f"Бесплатных сегодня: <b>{free_text}</b>\n"
            f"В запасе (платные): <b>{paid_analyses_left}</b>\n"
            f"Платные не сгорают — тратятся, когда кончится бесплатный лимит.\n\n"
            f"Пополни:",
            parse_mode="HTML",
            reply_markup=balance_keyboard()
        )
        return
    if text == "🎉 Праздники":
        reset_xmas_state(user_id)
        reset_holiday_state(user_id)
        from holidays import holidays_keyboard, HOLIDAYS_INTRO
        try:
            await message.answer_photo(
                photo="https://raw.githubusercontent.com/photorazbor/photo-bot/main/holidays/intro.jpg",
                caption=HOLIDAYS_INTRO,
                parse_mode="HTML",
                reply_markup=holidays_keyboard()
            )
        except Exception:
            await message.answer(
                HOLIDAYS_INTRO,
                parse_mode="HTML",
                reply_markup=holidays_keyboard()
            )
        return
    if text == "🔮 Карта дня":
        user_mode[user_id] = "daily"
        await message.answer(
            "🔮 <b>Карта дня</b>\n\n"
            "Каждый день Вселенная готовит для тебя послание.\n"
            "Одна карта — один день. Один ритуал.\n\n"
            "🆓 Первые 3 дня — бесплатно.\n"
            "💎 Дальше — 1 генерация с баланса.\n\n"
            "📸 Ритуал дня связан с фотографией —\n"
            "сделай кадр и разбери его через бота.\n\n"
            "Нажми, чтобы открыть карту 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Открыть карту дня", callback_data="daily_open")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            ])
        )
        user_mode[user_id] = "free"
        return
    if text == "📸 Разобрать фото":
        user_mode[user_id] = "free"
        flat_lay_active[user_id] = False
        can, left = _analysis_check_and_get(user_id) if not (user_id == 456504792 and test_mode) else (True, 999)
        left_text = "∞" if (user_id == 456504792 and test_mode) else str(left)
        if not can:
            await message.answer(
                "🔍 <b>Лимит анализов исчерпан.</b>\n\n"
                "Бесплатные обновляются каждый день — 5 штук.\n\n"
                "Хочешь больше сейчас? Купи пакет:",
                parse_mode="HTML",
                reply_markup=buy_analyses_keyboard()
            )
            return
        await message.answer(
            f"📸 Присылай фото — проанализирую композицию.\n\n"
            f"🔍 Осталось анализов сегодня: {left_text}",
            parse_mode="HTML"
        )
        return
    if text == "🎨 Стилизация":
        user_mode[user_id] = "style_photo"
        flat_lay_active[user_id] = False
        balance = get_balance(user_id)
        await message.answer(
            f"🎨 <b>Стилизация</b>\n\nПришли фото.\n\n"
            f"💰 Стоимость: 1 генерация\n💎 Твой баланс: {balance}",
            parse_mode="HTML"
        )
        return
    if text == "🏠 Главное меню":
        user_mode[user_id] = "free"
        flat_lay_active[user_id] = False
        editor_mode.pop(user_id, None)
        PHOTO_BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"
        balance = get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)
        await message.answer_photo(
            URLInputFile(f"{PHOTO_BASE}/start_banner.jpg"),
            caption=(
                f"👋 <b>Привет!</b>\n\n"
                f"📸 <b>Разбор фото:</b> бесплатно, 5 раз в день.\n"
                f"✨ <b>Улучшение:</b> ИИ исправит композицию.\n"
                f"✂️ <b>Редактор:</b> формат, ретушь.\n"
                f"📷 <b>Flat Lay:</b> предметная съёмка.\n"
                f"🎄 <b>Новогодняя фотосессия:</b> сказочные кадры.\n"
                f"🎓 <b>Мини-курс:</b> первый день бесплатно.\n\n"
                f"💎 <b>Твой баланс:</b> {balance_text}"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎉 Праздники", callback_data="holidays_start")],
                [InlineKeyboardButton(text="🔮 Карта дня", callback_data="daily_card")],
                [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
                [InlineKeyboardButton(text="🛠 Инструменты", callback_data="tools_menu")],
                [InlineKeyboardButton(text="🎯 Авторский разбор", callback_data="author_review")],
                [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
                [InlineKeyboardButton(text="💎 Баланс", callback_data="my_balance")],
                [InlineKeyboardButton(text="💛 Поддержать проект", callback_data="donate_menu")],
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
        await message.answer(
            "🎯 <b>Авторский разбор</b>\n\nЯ лично разберу твои фото.\n📷 До 5 фото\n💰 500 ₽",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить (500 ₽)", callback_data="pay_author_review")]
            ])
        )
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

    # === Удаляем Telegram-вебхук, чтобы polling работал без конфликта ===
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Telegram-вебхук удалён, работаем через polling")
    except Exception as e:
        logger.error(f"⚠️ Не удалось удалить вебхук: {e}")

    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    asyncio.create_task(daily_report())
    register_xmas_handlers(dp)
    register_reference_handlers(dp)
    register_daily_handlers(dp)
    register_holidays_handlers(dp)
    register_wedding_handlers(dp)
    register_prompt_handlers(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
