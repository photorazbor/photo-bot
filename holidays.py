"""
Праздники — День рождения и другие.
Логика как в xmas, но со своими данными.
"""
import logging

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)

logger = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"

# ===== ЛОКАЦИИ ДНЯ РОЖДЕНИЯ =====

BIRTHDAY_LOCATIONS = {
    "home": {
        "name": "Дома",
        "short": "🏠 Дома",
        "preview": f"{BASE}/holidays/birthday/locations/home.jpg",
        "intro": "Уютная домашняя обстановка: диван, шары, гирлянды, стол с тортом.",
    },
    "restaurant": {
        "name": "В ресторане",
        "short": "🍽 В ресторане",
        "preview": f"{BASE}/holidays/birthday/locations/restaurant.jpg",
        "intro": "Праздничный ресторан: стол со свечами, бокалы, красивая сервировка.",
    },
    "nature": {
        "name": "На природе",
        "short": "🌳 На природе",
        "preview": f"{BASE}/holidays/birthday/locations/nature.jpg",
        "intro": "Пикник на природе: зелень, шары, ленты, солнечный свет.",
    },
    "studio": {
        "name": "В студии",
        "short": "🎨 В студии",
        "preview": f"{BASE}/holidays/birthday/locations/studio.jpg",
        "intro": "Фотостудия: однотонный фон, профессиональный свет, шары, торт.",
    },
}

# ===== СЮЖЕТЫ ДНЯ РОЖДЕНИЯ =====

BIRTHDAY_SCENES = {
    "cake": {
        "name": "С тортом",
        "short": "🎂 С тортом",
        "preview": f"{BASE}/holidays/birthday/scenes/cake.jpg",
        "prompt": "с праздничным тортом со свечами в руках, задувают свечи, улыбаются",
    },
    "gifts": {
        "name": "С подарками",
        "short": "🎁 С подарками",
        "preview": f"{BASE}/holidays/birthday/scenes/gifts.jpg",
        "prompt": "с подарочными коробками в руках, разворачивают подарки, радуются",
    },
    "balloons": {
        "name": "С шарами",
        "short": "🎈 С шарами",
        "preview": f"{BASE}/holidays/birthday/scenes/balloons.jpg",
        "prompt": "с воздушными шарами в руках, разноцветные шары вокруг, веселье",
    },
    "toast": {
        "name": "С бокалами",
        "short": "🥂 С бокалами",
        "preview": f"{BASE}/holidays/birthday/scenes/toast.jpg",
        "prompt": "с бокалами в руках, произносят тост, улыбаются, праздничный стол",
    },
    "confetti": {
        "name": "С конфетти",
        "short": "🎉 С конфетти",
        "preview": f"{BASE}/holidays/birthday/scenes/confetti.jpg",
        "prompt": "в момент взрыва конфетти, разноцветные блёстки в воздухе, радость",
    },
}

# ===== ОБРАЗЫ ДНЯ РОЖДЕНИЯ =====

BIRTHDAY_OUTFITS = {
    "own": {
        "name": "Своя одежда",
        "short": "👕 Своя одежда",
        "preview": f"{BASE}/holidays/birthday/outfits/own.jpg",
        "prompt": "оставить одежду с исходного фото без изменений — тот же цвет, фасон, ткань, аксессуары",
    },
    "elegant": {
        "name": "Нарядный образ",
        "short": "👗 Нарядный",
        "preview": f"{BASE}/holidays/birthday/outfits/elegant.jpg",
        "prompt": (
            "в нарядной праздничной одежде: платье или костюм, "
            "элегантно, но без излишней формальности. "
            "Свободный крой, комфортно, современно."
        ),
    },
    "themed": {
        "name": "Тематический",
        "short": "🎩 Тематический",
        "preview": f"{BASE}/holidays/birthday/outfits/themed.jpg",
        "prompt": (
            "в тематической праздничной одежде: праздничный колпак, "
            "яркая футболка с надписью, забавные аксессуары. "
            "Весело, по-праздничному, но не пошло."
        ),
    },
}

# ===== ФОРМАТЫ =====

BIRTHDAY_FORMATS = {
    "original": {"name": "📐 Исходный", "short": "📐 Исходный", "desc": "как на исходном фото"},
    "1_1": {"name": "📱 1:1 (квадрат)", "short": "📱 1:1 (квадрат)", "desc": "квадратная композиция"},
    "3_4": {"name": "📱 3:4 (вертикаль)", "short": "📱 3:4 (вертикаль)", "desc": "вертикальная композиция"},
    "4_3": {"name": "🖼 4:3 (горизонт)", "short": "🖼 4:3 (горизонт)", "desc": "горизонтальная композиция"},
    "4_5": {"name": "📱 4:5 (Instagram)", "short": "📱 4:5 (Instagram)", "desc": "вертикаль для Instagram"},
    "9_16": {"name": "📱 9:16 (сторис)", "short": "📱 9:16 (сторис)", "desc": "полная вертикаль для сторис"},
}

# ===== СТИЛИЗАЦИИ ДНЯ РОЖДЕНИЯ =====

BIRTHDAY_STYLES = {
    "realistic": {
        "name": "🎬 Реалистичное фото",
        "short": "🎬 Реалистичное",
        "prompt": "",
    },
    "soviet_card": {
        "name": "🎄 Советская открытка",
        "short": "🎄 Советская открытка",
        "prompt": (
            "СТИЛИЗАЦИЯ: советская праздничная открытка 1960–70-х годов. "
            "ЖИВОПИСНАЯ ИЛЛЮСТРАЦИЯ, нарисованная от руки кистью или акварелью. "
            "НЕ фотография, НЕ цифровой вектор. "
            "Видны мазки кисти, мягкие акварельные заливки, плавные переходы. "
            "Линии мягкие, чуть неровные — как от руки. "
            "Лёгкая плёночная зернистость как у типографской печати. "
            "БЕЗ текстуры старой бумаги, БЕЗ потёртостей, БЕЗ заломов. "
            "ЦВЕТА: приглушённые, тёплые, винтажные, но НЕ выцветшие в жёлтый. "
            "Виньетка по краям — мягкое затемнение. "
            "ЛЮДИ: нарисованные, лица узнаваемы с исходного фото, мягко. "
            "Одежда — по выбранному образу, в советском стиле. "
            "ДЕКОР: цветы, ленты, шары, торт, праздничный стол, воздушные шарики. "
            "ТЕКСТ: крупный рукописный «С днём рождения!» курсивом, "
            "красный или тёмно-синий, вверху или внизу. "
            "ГЛАВНОЕ: живописная ручная работа, а НЕ цифровая иллюстрация."
        ),
    },
    "soviet_cartoon": {
        "name": "📺 Советский мультик",
        "short": "📺 Советский мультик",
        "prompt": (
            "СТИЛИЗАЦИЯ: советская рисованная анимация 1960–70-х годов. "
            "ЭТО РИСОВАННЫЙ МУЛЬТФИЛЬМ, А НЕ ФОТОГРАФИЯ. "
            "Акварельные фоны, рисованные плоские персонажи, мягкие пастельные тона, "
            "контурная обводка, тёплый свет, наивный добрый стиль."
        ),
    },
    "disney": {
        "name": "🐭 Диснеевский мультик",
        "short": "🐭 Диснеевский",
        "prompt": (
            "СТИЛИЗАЦИЯ: современная диснеевская 3D-анимация (Pixar/Disney). "
            "ЭТО 3D-МУЛЬТФИЛЬМ, А НЕ ФОТОГРАФИЯ. "
            "Мультяшные 3D-персонажи с большими глазами, мягкие округлые формы, "
            "гладкие рендер-поверхности, яркие тёплые цвета."
        ),
    },
    "comics": {
        "name": "💥 Комикс с раскадровкой",
        "short": "💥 Комикс",
        "prompt": (
            "СТИЛИЗАЦИЯ: праздничный комикс с раскадровкой из 3 панелей на одной картинке. "
            "ЭТО КОМИКС, А НЕ ФОТОГРАФИЯ. "
            "Три кадра одной истории: на всех — те же люди, разные ракурсы или моменты. "
            "ЯРКИЙ РИСОВАННЫЙ КОМИКС-СТИЛЬ: чёрные жирные контуры, плоские яркие цвета, "
            "штриховка (halftone dots), динамичные позы. "
            "В каждой панели — короткая надпись на РУССКОМ языке. "
            "ЖЁСТКОЕ ПРАВИЛО ПО ЛЮДЯМ: "
            "посчитай ТОЧНОЕ количество людей на исходном фото. "
            "На КАЖДОЙ из 3 панелей должно быть РОВНО столько же людей. "
            "НЕ добавляй новых персонажей. НЕ убирай никого. "
            "ЖЁСТКОЕ ПРАВИЛО ПО ОДЕЖДЕ И ВНЕШНОСТИ: "
            "на ВСЕХ 3 панелях у каждого персонажа ОДНА И ТА ЖЕ ОДЕЖДА. "
            "НЕ меняй одежду, причёску, цвет волос между панелями."
        ),
    },
    "painting": {
        "name": "🎨 Картина",
        "short": "🎨 Картина",
        "prompt": (
            "СТИЛИЗАЦИЯ: живописная картина маслом. "
            "Видимые мазки кисти, насыщенные цвета, художественная текстура. "
            "Стиль как у классической живописи. "
            "Сохрани всех людей и композицию, но в виде картины."
        ),
    },
}

# ===== СОСТОЯНИЕ =====
holiday_state = {}
holiday_awaiting_photo = set()
holiday_awaiting_custom = {}


def is_user_in_holiday_flow(user_id: int) -> bool:
    return user_id in holiday_state and user_id not in holiday_awaiting_photo


def reset_holiday_state(user_id: int):
    holiday_state.pop(user_id, None)
    holiday_awaiting_photo.discard(user_id)
    holiday_awaiting_custom.pop(user_id, None)


# ===== КЛАВИАТУРЫ =====

def holidays_keyboard():
    """Главное меню праздников."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎄 Новый год", callback_data="xmas_start")],
        [InlineKeyboardButton(text="🎂 День рождения", callback_data="holiday_birthday")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])


def bd_locations_keyboard():
    rows = []
    for key, loc in BIRTHDAY_LOCATIONS.items():
        rows.append([InlineKeyboardButton(text=loc["short"], callback_data=f"holiday_bd_loc_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bd_scenes_keyboard():
    rows = []
    for key, scene in BIRTHDAY_SCENES.items():
        rows.append([InlineKeyboardButton(text=scene["short"], callback_data=f"holiday_bd_scene_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_bd_back_loc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bd_outfits_keyboard():
    rows = []
    for key, outfit in BIRTHDAY_OUTFITS.items():
        rows.append([InlineKeyboardButton(text=outfit["short"], callback_data=f"holiday_bd_outfit_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_bd_back_scene")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bd_formats_keyboard():
    rows = []
    for key, fmt in BIRTHDAY_FORMATS.items():
        rows.append([InlineKeyboardButton(text=fmt["short"], callback_data=f"holiday_bd_fmt_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_bd_back_outfit")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bd_styles_keyboard():
    rows = []
    for key, style in BIRTHDAY_STYLES.items():
        rows.append([InlineKeyboardButton(text=style["short"], callback_data=f"holiday_bd_style_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_bd_back_fmt")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bd_upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="holiday_bd_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="holiday_bd_back_style")],
    ])


def bd_result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data="holiday_bd_regen")],
        [InlineKeyboardButton(text="📷 Загрузить другое фото", callback_data="holiday_bd_upload_again")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

HOLIDAYS_INTRO = (
    "🎉 <b>Праздники</b>\n\n"
    "Сделаю тебе праздничную фотосессию с твоим лицом.\n\n"
    "Выбери праздник:"
)

BIRTHDAY_INTRO = (
    "🎂 <b>День рождения</b>\n\n"
    "Соберу тебя на празднике: торт, шары, подарки, конфетти, "
    "тёплый свет, улыбки.\n\n"
    "📸 Шаги:\n"
    "1. Локация\n"
    "2. Сюжет\n"
    "3. Образ\n"
    "4. Формат\n"
    "5. Стиль\n\n"
    "💎 Стоимость: 1 генерация\n\n"
    "Начнём!"
)

BD_CHOOSE_LOCATION = "📍 <b>Шаг 1 из 5. Выбери локацию:</b>"
BD_CHOOSE_SCENE = "🎬 <b>Шаг 2 из 5. Выбери сюжет:</b>"
BD_CHOOSE_OUTFIT = "👗 <b>Шаг 3 из 5. Выбери образ:</b>"
BD_CHOOSE_FORMAT = "📐 <b>Шаг 4 из 5. Выбери формат:</b>"
BD_CHOOSE_STYLE = "🎨 <b>Шаг 5 из 5. Выбери стиль:</b>"
BD_UPLOAD = (
    "📸 <b>Пришли фото</b>\n\n"
    "Требования:\n"
    "• Все видны по грудь, по пояс или по колено\n"
    "• Лица крупные, чёткие, без сильных теней\n"
    "• Хорошее освещение\n\n"
    "⚠️ Чем крупнее лица — тем точнее сохранятся.\n\n"
    "После фото — сгенерирую 1 кадр. Будет 1 бесплатная перегенерация."
)


# ===== ВСПОМОГАТЕЛЬНОЕ =====

async def _send_previews(message, previews: list, caption: str, keyboard):
    photos = [p for p in previews if p]
    if photos:
        try:
            media = [InputMediaPhoto(media=url) for url in photos[:10]]
            await message.answer_media_group(media=media)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить превью: {e}")
    await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)


# ===== РЕГИСТРАЦИЯ =====

def register_holidays_handlers(dp):
    """Регистрирует обработчики праздников."""

    @dp.callback_query(F.data == "holidays_start")
    async def holidays_start(callback: CallbackQuery):
        await callback.answer()
        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/holidays/intro.jpg",
                caption=HOLIDAYS_INTRO,
                parse_mode="HTML",
                reply_markup=holidays_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                HOLIDAYS_INTRO,
                parse_mode="HTML",
                reply_markup=holidays_keyboard(),
            )

    # ===== ДЕНЬ РОЖДЕНИЯ =====

    @dp.callback_query(F.data == "holiday_birthday")
    async def holiday_birthday(callback: CallbackQuery):
        await callback.answer()
        from main import get_balance, test_mode, buy_generations_keyboard
        user_id = callback.from_user.id
        balance = get_balance(user_id)
        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            return
        holiday_state[user_id] = {"holiday": "birthday"}
        previews = [loc["preview"] for loc in BIRTHDAY_LOCATIONS.values()]
        await _send_previews(
            callback.message, previews,
            BIRTHDAY_INTRO + "\n\n" + BD_CHOOSE_LOCATION,
            bd_locations_keyboard()
        )

    # ===== ШАГ 1: ЛОКАЦИЯ =====

    @dp.callback_query(F.data.startswith("holiday_bd_loc_"))
    async def bd_location(callback: CallbackQuery):
        await callback.answer()
        loc_key = callback.data.replace("holiday_bd_loc_", "")
        if loc_key not in BIRTHDAY_LOCATIONS:
            await callback.message.answer("❌ Локация не найдена.")
            return
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {"holiday": "birthday"})
        state["location"] = loc_key
        holiday_state[user_id] = state
        previews = [s["preview"] for s in BIRTHDAY_SCENES.values()]
        await _send_previews(callback.message, previews, BD_CHOOSE_SCENE, bd_scenes_keyboard())

    @dp.callback_query(F.data == "holiday_bd_back_loc")
    async def bd_back_loc(callback: CallbackQuery):
        await callback.answer()
        previews = [loc["preview"] for loc in BIRTHDAY_LOCATIONS.values()]
        await _send_previews(callback.message, previews, BD_CHOOSE_LOCATION, bd_locations_keyboard())

    # ===== ШАГ 2: СЮЖЕТ =====

    @dp.callback_query(F.data.startswith("holiday_bd_scene_"))
    async def bd_scene(callback: CallbackQuery):
        await callback.answer()
        scene_key = callback.data.replace("holiday_bd_scene_", "")
        if scene_key not in BIRTHDAY_SCENES:
            await callback.message.answer("❌ Сюжет не найден.")
            return
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        state["scene"] = scene_key
        holiday_state[user_id] = state
        previews = [o["preview"] for o in BIRTHDAY_OUTFITS.values()]
        await _send_previews(callback.message, previews, BD_CHOOSE_OUTFIT, bd_outfits_keyboard())

    @dp.callback_query(F.data == "holiday_bd_back_scene")
    async def bd_back_scene(callback: CallbackQuery):
        await callback.answer()
        previews = [s["preview"] for s in BIRTHDAY_SCENES.values()]
        await _send_previews(callback.message, previews, BD_CHOOSE_SCENE, bd_scenes_keyboard())

    # ===== ШАГ 3: ОБРАЗ =====

    @dp.callback_query(F.data.startswith("holiday_bd_outfit_"))
    async def bd_outfit(callback: CallbackQuery):
        await callback.answer()
        outfit_key = callback.data.replace("holiday_bd_outfit_", "")
        if outfit_key not in BIRTHDAY_OUTFITS:
            await callback.message.answer("❌ Образ не найден.")
            return
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        state["outfit"] = outfit_key
        holiday_state[user_id] = state
        await callback.message.answer(BD_CHOOSE_FORMAT, parse_mode="HTML", reply_markup=bd_formats_keyboard())

    @dp.callback_query(F.data == "holiday_bd_back_outfit")
    async def bd_back_outfit(callback: CallbackQuery):
        await callback.answer()
        previews = [o["preview"] for o in BIRTHDAY_OUTFITS.values()]
        await _send_previews(callback.message, previews, BD_CHOOSE_OUTFIT, bd_outfits_keyboard())

    # ===== ШАГ 4: ФОРМАТ =====

    @dp.callback_query(F.data.startswith("holiday_bd_fmt_"))
    async def bd_format(callback: CallbackQuery):
        await callback.answer()
        fmt_key = callback.data.replace("holiday_bd_fmt_", "")
        if fmt_key not in BIRTHDAY_FORMATS:
            await callback.message.answer("❌ Формат не найден.")
            return
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        state["format"] = fmt_key
        holiday_state[user_id] = state
        await callback.message.answer(BD_CHOOSE_STYLE, parse_mode="HTML", reply_markup=bd_styles_keyboard())

    @dp.callback_query(F.data == "holiday_bd_back_fmt")
    async def bd_back_fmt(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(BD_CHOOSE_FORMAT, parse_mode="HTML", reply_markup=bd_formats_keyboard())

    # ===== ШАГ 5: СТИЛЬ =====

    @dp.callback_query(F.data.startswith("holiday_bd_style_"))
    async def bd_style(callback: CallbackQuery):
        await callback.answer()
        style_key = callback.data.replace("holiday_bd_style_", "")
        if style_key not in BIRTHDAY_STYLES:
            await callback.message.answer("❌ Стиль не найден.")
            return
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        state["style"] = style_key
        holiday_state[user_id] = state
        await _show_upload(callback.message, state)

    @dp.callback_query(F.data == "holiday_bd_back_style")
    async def bd_back_style(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(BD_CHOOSE_STYLE, parse_mode="HTML", reply_markup=bd_styles_keyboard())

    # ===== СВОДКА + ФОТО =====

    async def _show_upload(msg, state):
        loc = BIRTHDAY_LOCATIONS.get(state.get("location", ""))
        loc_name = loc["name"] if loc else "—"
        scene = BIRTHDAY_SCENES.get(state.get("scene", ""))
        scene_name = scene["name"] if scene else "—"
        outfit = BIRTHDAY_OUTFITS.get(state.get("outfit", ""))
        outfit_name = outfit["name"] if outfit else "—"
        fmt = BIRTHDAY_FORMATS.get(state.get("format", ""))
        fmt_name = fmt["name"] if fmt else "—"
        style = BIRTHDAY_STYLES.get(state.get("style", ""))
        style_name = style["name"] if style else "—"

        caption = (
            "📋 <b>Твой выбор:</b>\n\n"
            f"📍 Локация: {loc_name}\n"
            f"🎬 Сюжет: {scene_name}\n"
            f"👗 Образ: {outfit_name}\n"
            f"📐 Формат: {fmt_name}\n"
            f"🎨 Стиль: {style_name}\n\n"
            f"{BD_UPLOAD}"
        )
        await msg.answer(caption, parse_mode="HTML", reply_markup=bd_upload_keyboard())

    # ===== ЗАГРУЗКА ФОТО =====

    @dp.callback_query(F.data == "holiday_bd_upload")
    async def bd_upload(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        state["regen_done"] = False
        holiday_state[user_id] = state
        holiday_awaiting_photo.add(user_id)
        logger.info(f"✅ holiday_bd_upload: user={user_id}")
        await callback.message.answer("📸 Жду фото. Пришли одно фото.")

    @dp.callback_query(F.data == "holiday_bd_upload_again")
    async def bd_upload_again(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        reset_holiday_state(user_id)
        from main import get_balance, test_mode, buy_generations_keyboard
        balance = get_balance(user_id)
        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            return
        holiday_state[user_id] = {"holiday": "birthday"}
        previews = [loc["preview"] for loc in BIRTHDAY_LOCATIONS.values()]
        await _send_previews(
            callback.message, previews,
            "🔄 Начинаем новую фотосессию.\n\n" + BD_CHOOSE_LOCATION,
            bd_locations_keyboard()
        )

    # ===== ПЕРЕГЕНЕРАЦИЯ =====

    @dp.callback_query(F.data == "holiday_bd_regen")
    async def bd_regen(callback: CallbackQuery):
        user_id = callback.from_user.id
        state = holiday_state.get(user_id, {})
        if not state.get("photo"):
            await callback.answer("❌ Нет фото. Загрузи заново.", show_alert=True)
            return
        if state.get("regen_done"):
            await callback.answer(
                "Перегенерация уже использована. Загрузи новое фото.",
                show_alert=True,
            )
            return
        state["regen_done"] = True
        holiday_state[user_id] = state
        await callback.answer("🎨 Генерирую другой вариант...")
        await _generate_and_send(callback.message, user_id, state)


# ===== ОБРАБОТКА ФОТО =====

async def handle_holiday_photo(message: Message, user_id: int, image_bytes: bytes):
    """Вызывается из main.py, когда пользователь в режиме holiday_awaiting_photo."""
    state = holiday_state.get(user_id, {})
    state["photo"] = image_bytes
    state["regen_done"] = False
    holiday_state[user_id] = state
    holiday_awaiting_photo.discard(user_id)
    await message.answer("✅ Фото получено!")
    await _generate_and_send(message, user_id, state)


# ===== ГЕНЕРАЦИЯ =====

def _build_prompt(state: dict) -> str | None:
    loc_key = state.get("location")
    loc = BIRTHDAY_LOCATIONS.get(loc_key)
    scene_key = state.get("scene")
    scene = BIRTHDAY_SCENES.get(scene_key)
    outfit_key = state.get("outfit")
    outfit = BIRTHDAY_OUTFITS.get(outfit_key)

    if not (loc and scene and outfit):
        return None

    location_text = loc["intro"]
    scene_text = scene["prompt"]
    outfit_text = outfit["prompt"]

    birthday_lock = (
        "СМЫСЛ КАДРА — ПОЗДРАВЛЕНИЕ: "
        "Все люди на фото — поздравляют. "
        "Они вместе поздравляют кого-то (кого нет в кадре). "
        "НИКТО из них НЕ именинник. "
        "НЕ выделяй никого как главного. "
        "НЕ назначай именинника. "
        "Все — равные участники поздравления. "
        "В руках: торт, шары, подарки, цветы — как атрибуты поздравления, "
        "а НЕ как «подарок имениннику». "
        "Все улыбаются, радуются, празднуют вместе. "
        "Если есть текст «С днём рождения!» — это открытка от всех, кто в кадре. "
    )

    face_lock = (
        "КОЛИЧЕСТВО ЛЮДЕЙ: посчитай ТОЧНО, сколько людей на исходном фото. "
        "На новой картинке — РОВНО СТОЛЬКО ЖЕ. "
        "НЕ добавляй никого. НЕ убирай никого. НЕ заменяй. "
        "Все люди с исходного фото — на новой картинке. "
        "ЗАПРЕЩЕНО: прохожие, силуэты, фигуры вдалеке. "
    )

    outfit_lock = (
        f"ОДЕЖДА: {outfit_text}. "
        "Стиль современный, свободный, оверсайз. "
        "ЗАПРЕЩЕНО: скинни, короткие юбки, мини-платья, спортивные штаны, "
        "вызывающие наряды, устаревший стиль 2000-х. "
        "НУЖНО: свободные брюки, джинсы, оверсайз-свитера, свободные платья."
    )

    frame_lock = (
        "КАДР: по грудь, по пояс или по колено. Ноги ниже колена не видны. "
        "Без обуви. Не делай полный рост. "
    )

    pose_lock = (
        "ПОЗА: естественная, живая, как на реальном фото — не сток. "
        "Руки заняты: торт, подарок, шары, бокал. "
        "Поза — случайный момент, а не позирование. "
        "Живое, тёплое, человеческое фото."
    )

    style_key_pre = state.get("style", "realistic")
    is_art_style = style_key_pre in ("soviet_card", "soviet_cartoon", "disney", "comics", "painting")

    if is_art_style:
        realism_lock = ""
        art_style_lock = (
            "ХУДОЖЕСТВЕННЫЙ СТИЛЬ — ЭТО НЕ ФОТОГРАФИЯ. "
            "Изображение должно быть РИСОВАННЫМ, а НЕ фотореалистичным. "
            "Запрещено: фотореализм, кожа с порами, реалистичные детали. "
            "Нужно: рисованная иллюстрация."
        )
        face_realism_lock = ""
        emotion_lock = ""
    else:
        realism_lock = (
            "РЕАЛИЗМ: фото должно выглядеть как настоящий кадр, "
            "а НЕ как рендер нейросети. "
            "ЗАПРЕЩЕНО: слишком гладкая кожа, идеальная симметрия, кукольные лица. "
            "НУЖНО: лёгкая асимметрия, естественные тени, живая фотография."
        )
        art_style_lock = ""
        face_realism_lock = (
            "ЛИЦА — ПРИОРИТЕТ №1: сходство с исходным фото — ГЛАВНОЕ. "
            "Сохрани у каждого человека: форму лица, брови, глаза, нос, губы, "
            "веснушки или родинки (или их отсутствие), причёску, цвет волос, "
            "пол, возраст, тон кожи. "
            "НЕ ретушируй, НЕ сглаживай кожу, НЕ выравнивай тон. "
            "НЕ добавляй веснушки, если их нет. НЕ убирай родинки. "
            "НЕ меняй брови, глаза, нос, губы, овал лица. "
            "Если несколько людей — каждому его лицо, не смешивай. "
            "ИНТЕГРАЦИЯ: лицо освещено светом сцены. "
            "Лица — ЧАСТЬ кадра, а не аппликация. "
            "Лица — в фокусе и узнаваемы."
        )
        emotion_lock = (
            "ЭМОЦИИ — ЛЁГКИЕ, ЕСТЕСТВЕННЫЕ, КАК НА ИСХОДНОМ: "
            "Сохрани выражение лица с исходного фото. "
            "Если человек не улыбается — добавь ЛЁГКУЮ, едва заметную улыбку "
            "уголками губ. НЕ широкую, НЕ во все зубы. "
            "Если на исходном лёгкая улыбка — оставь лёгкой. "
            "Если широкая — сделай чуть сдержаннее. "
            "НЕ поднимай сильно брови. НЕ расширяй глаза. "
            "Глаза — живые, тёплые, но без «глянца». "
            "Поза и настроение — праздничные, "
            "но мимика — спокойная и естественная. "
            "Лицо должно остаться УЗНАВАЕМЫМ — "
            "не переделывай его улыбкой."
        )

    location_lock = (
        f"ЛОКАЦИЯ: {location_text}. {scene_text}. "
        "Праздничная атмосфера, тёплый свет."
    )

    accessories_lock = (
        "УКРАШЕНИЯ: по умолчанию НЕ рисуй никаких украшений. "
        "Если на исходном фото украшений не видно — НЕ добавляй их. "
        "Если видно — сохрани в точности."
    )

    atmosphere_lock = (
        "АТМОСФЕРА: праздничная, тёплая, радостная. "
        "Шары, конфетти, ленты, гирлянды, торт, подарки. "
        "Мягкий свет, уют и веселье. "
        "Лёгкий боке, тёплые оттенки."
    )

    from main import get_size_for_format
    fmt_key = state.get("format", "1_1")
    fmt = BIRTHDAY_FORMATS.get(fmt_key, BIRTHDAY_FORMATS["1_1"])
    photo_bytes = state.get("photo")
    img_size = get_size_for_format(fmt_key, photo_bytes)

    format_lock = (
        f"ФОРМАТ КАДРА: {fmt['name']}, размер {img_size}. "
        f"Построй КРАСИВУЮ ГАРМОНИЧНУЮ композицию под этот формат — {fmt['desc']}. "
        "Кадрирование людей выбери САМ: по грудь, по пояс или по колено — как гармонично смотрится. "
        "Главное — чтобы композиция была ЦЕЛЬНОЙ, БЕЗ пустых полос, БЕЗ обрезов посередине фигуры. "
        f"Верни изображение РОВНО {img_size} пикселей. "
    )

    style_key = state.get("style", "realistic")
    style = BIRTHDAY_STYLES.get(style_key, BIRTHDAY_STYLES["realistic"])
    style_lock = style["prompt"] if style["prompt"] else ""

    if is_art_style:
        final_line = "Финальный стиль: рисованная иллюстрация."
    else:
        final_line = "Финальный стиль: атмосферно, тепло, живо, реалистично."

    full = (
        f"Праздничная иллюстрация. "
        f"{birthday_lock}"
        f"{face_lock}"
        f"{face_realism_lock}"
        f"{emotion_lock}"
        f"{outfit_lock}"
        f"{accessories_lock}"
        f"{frame_lock}"
        f"{pose_lock}"
        f"{location_lock}"
        f"{atmosphere_lock}"
        f"{realism_lock}"
        f"{art_style_lock}"
        f"{format_lock}"
        f"{style_lock}"
        f"{final_line} "
        f"ОБЯЗАТЕЛЬНО: размер изображения РОВНО {img_size}. "
        f"Не квадрат и не стандарт — именно {fmt['name']}. "
        f"Композиция выстроена под этот формат, "
        f"главный объект в кадре, без пустых полос по краям."
    )
    return full


async def _generate_and_send(message: Message, user_id: int, state: dict):
    from ai_service import generate_image
    from main import get_balance, spend_generation, test_mode, buy_generations_keyboard

    photo = state.get("photo")
    if not photo:
        await message.answer("❌ Нет фото. Загрузи заново.")
        return

    is_regen = state.get("regen_done", False)

    if not is_regen:
        if not spend_generation(user_id):
            await message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            return

    full_prompt = _build_prompt(state)
    if not full_prompt:
        await message.answer("❌ Не все параметры выбраны. Начни заново: /start")
        return

    await message.answer("🎨 Генерирую кадр... Обычно это занимает до минуты.")

    logger.info(f"🎨 holiday генерация: user={user_id}, regen={is_regen}")

    try:
        img = generate_image(photo, full_prompt)
        if not img:
            logger.warning("⚠️ holiday: первая попытка не удалась, пробую ещё раз")
            await message.answer("🔄 Сервис задумался, пробую ещё раз...")
            img = generate_image(photo, full_prompt)
    except Exception as e:
        logger.exception(f"❌ holiday: исключение при генерации: {e}")
        img = None

    if not img:
        logger.warning(f"❌ holiday: generate_image вернул None")
        state["regen_done"] = False
        holiday_state[user_id] = state
        await message.answer(
            "😔 Не удалось сгенерировать кадр.\n\n"
            "✅ Попытка НЕ списана.\n"
            "🔄 Нажми «Перегенерировать» ещё раз."
        )
        return

    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    try:
        await message.answer_photo(
            BufferedInputFile(img, filename="holiday.jpg"),
            caption=f"🎉 <b>Готово!</b>\n\n💎 Баланс: {balance_text}",
            parse_mode="HTML",
            reply_markup=bd_result_keyboard(),
        )
    except Exception as e:
        logger.exception(f"❌ holiday: ошибка отправки фото: {e}")
        await message.answer("❌ Не удалось отправить фото.")
