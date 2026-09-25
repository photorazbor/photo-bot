"""
Свадьба — пригласительные открытки и пригласительные с фото.
Логика как в holidays, но со своими данными.
"""
import logging

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logger = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main/examples"

# ===== РЕЖИМЫ =====

WEDDING_MODES = {
    "no_photo": {
        "name": "💌 Открытка без фото",
        "short": "💌 Открытка без фото",
        "desc": "Готовая свадебная открытка. Без фото. Место под ручную подпись.",
        "example_folder": "no_photo",
    },
    "no_photo_car": {
        "name": "🚗 Открытка с ретро-авто",
        "short": "🚗 Открытка с ретро-авто",
        "desc": "Открытка с винтажным автомобилем, цветами и лентами. Без фото. Место под подпись.",
        "example_folder": "no_photo_car",
    },
    "with_photo": {
        "name": "📸 Пригласительное с фото",
        "short": "📸 С фото",
        "desc": "Пригласительное с вашим фото. Лица сохраняются, стиль — как у открытки.",
        "example_folder": "with_photo",
    },
}

# ===== СТИЛИ =====

WEDDING_STYLES = {
    "botanic": {
        "name": "🌿 Ботаника",
        "short": "🌿 Ботаника",
        "prompt": (
            "СТИЛЬ: ботаническая свадебная иллюстрация. "
            "Акварельно-графичная живопись, мягкие линии, тёплые естественные тона. "
            "Палитра: зелёный, беж, пудровый, эвкалипт, олива. "
            "Декор: ветки эвкалипта, оливы, сухоцветы, злаки, лёгкие цветочные мотивы. "
            "Люди — нарисованные в этом же стиле: мягкая живопись, "
            "узнаваемые черты, без фотореализма."
        ),
    },
    "watercolor": {
        "name": "🎨 Акварель",
        "short": "🎨 Акварель",
        "prompt": (
            "СТИЛЬ: нежная акварельная живопись. "
            "Полупрозрачные слои краски, мягкие переходы, лёгкие мазки. "
            "Палитра: нежно-розовый, голубой, лаванда, кремовый. "
            "Декор: мягкие цветочные пятна, размытые линии, воздушность. "
            "Люди — нарисованные акварелью, лица мягкие, узнаваемые, без фотореализма."
        ),
    },
    "minimal": {
        "name": "⬜ Минимализм",
        "short": "⬜ Минимализм",
        "prompt": (
            "СТИЛЬ: современный минимализм. "
            "Графичная линия, чёткие контуры, минимум деталей, плоские цветовые пятна. "
            "Палитра: 2–3 цвета — чёрный, белый, акцент (охра, терракота, олива). "
            "Декор: один штрих, много воздуха, чистая геометрия. "
            "Люди — нарисованные линией, узнаваемые, без лишних деталей."
        ),
    },
    "artdeco": {
        "name": "✨ Арт-деко",
        "short": "✨ Арт-деко",
        "prompt": (
            "СТИЛЬ: арт-деко 1920-х. "
            "Геометричная стилизация, элегантные вытянутые пропорции, "
            "чёткие линии, золото, лоск. "
            "Палитра: чёрный, золото, изумруд, бордо. "
            "Декор: геометрические орнаменты, веера, лучи, золотые рамки. "
            "Люди — нарисованные в стиле арт-деко: гламурно, элегантно, узнаваемо."
        ),
    },
    "vintage": {
        "name": "📜 Винтаж",
        "short": "📜 Винтаж",
        "prompt": (
            "СТИЛЬ: винтажная открытка начала XX века. "
            "Сепия, мягкая живопись, чуть размытые контуры, лёгкая зернистость. "
            "Палитра: сепия, крем, ржавчина, тёмно-зелёный. "
            "Декор: кружево, лёгкие потёртости, винтажные розы, тонкая рамка. "
            "Люди — нарисованные в винтажном стиле, узнаваемые, с лёгкой зернистостью."
        ),
    },
}

# ===== ФОРМАТЫ =====

WEDDING_FORMATS = {
    "original": {"name": "📐 Исходный", "short": "📐 Исходный", "desc": "как на исходном фото"},
    "1_1": {"name": "📱 1:1 (квадрат)", "short": "📱 1:1 (квадрат)", "desc": "квадратная композиция"},
    "3_4": {"name": "📱 3:4 (вертикаль)", "short": "📱 3:4 (вертикаль)", "desc": "вертикальная композиция"},
    "4_3": {"name": "🖼 4:3 (горизонт)", "short": "🖼 4:3 (горизонт)", "desc": "горизонтальная композиция"},
    "4_5": {"name": "📱 4:5 (Instagram)", "short": "📱 4:5 (Instagram)", "desc": "вертикаль для Instagram"},
    "9_16": {"name": "📱 9:16 (сторис)", "short": "📱 9:16 (сторис)", "desc": "полная вертикаль для сторис"},
}

# ===== СОСТОЯНИЕ =====

wedding_state = {}
wedding_awaiting_photo = set()
wedding_awaiting_custom = {}


def reset_wedding_state(user_id: int):
    wedding_state.pop(user_id, None)
    wedding_awaiting_photo.discard(user_id)
    wedding_awaiting_custom.pop(user_id, None)


def is_user_in_wedding_flow(user_id: int) -> bool:
    return user_id in wedding_state and user_id not in wedding_awaiting_photo


# ===== КЛАВИАТУРЫ =====

def wedding_intro_keyboard():
    rows = []
    for key, mode in WEDDING_MODES.items():
        rows.append([InlineKeyboardButton(text=mode["short"], callback_data=f"wedding_mode_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="holidays_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_styles_keyboard():
    rows = []
    for key, style in WEDDING_STYLES.items():
        rows.append([InlineKeyboardButton(text=style["short"], callback_data=f"wedding_style_{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Свой стиль", callback_data="wedding_custom_style")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_formats_keyboard():
    rows = []
    for key, fmt in WEDDING_FORMATS.items():
        rows.append([InlineKeyboardButton(text=fmt["short"], callback_data=f"wedding_fmt_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_style")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="wedding_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_format")],
    ])


def wedding_result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data="wedding_regen")],
        [InlineKeyboardButton(text="💍 Новая открытка", callback_data="wedding_start")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

WEDDING_INTRO = (
    "💍 <b>Свадебные пригласительные</b>\n\n"
    "Создам красивую свадебную открытку или пригласительное.\n\n"
    "<b>Что можно сделать:</b>\n"
    "💌 <b>Открытка без фото</b> — готовая свадебная открытка "
    "с местом под ручную подпись. Распечатай и впиши имена от руки.\n\n"
    "🚗 <b>Открытка с ретро-авто</b> — то же, но с винтажным автомобилем, "
    "цветами и лентами. Красиво, стильно, по-свадебному.\n\n"
    "📸 <b>Пригласительное с фото</b> — пригласительное с вашим фото. "
    "Лица сохраняются, стиль — как у открытки.\n\n"
    "Выбери, что хочешь создать:"
)

WEDDING_CHOOSE_STYLE = "🎨 <b>Шаг 1 из 3. Выбери стиль:</b>"
WEDDING_CHOOSE_FORMAT = "📐 <b>Шаг 2 из 3. Выбери формат кадра:</b>"
WEDDING_UPLOAD = (
    "📸 <b>Шаг 3 из 3. Пришли фото</b>\n\n"
    "Требования:\n"
    "• Все видны по грудь, по пояс или по колено\n"
    "• Лица крупные, чёткие, без сильных теней\n"
    "• Хорошее освещение\n\n"
    "⚠️ Чем крупнее лица — тем точнее сохранятся.\n\n"
    "После фото — сгенерирую 1 открытку. Будет 1 бесплатная перегенерация."
)


# ===== РЕГИСТРАЦИЯ =====

def register_wedding_handlers(dp):
    """Регистрирует обработчики «Свадьбы»."""

    @dp.callback_query(F.data == "wedding_start")
    async def wedding_start(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        reset_wedding_state(user_id)

        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/holidays/wedding/intro.jpg",
                caption=WEDDING_INTRO,
                parse_mode="HTML",
                reply_markup=wedding_intro_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                WEDDING_INTRO,
                parse_mode="HTML",
                reply_markup=wedding_intro_keyboard(),
            )

    @dp.callback_query(F.data.startswith("wedding_mode_"))
    async def wedding_mode(callback: CallbackQuery):
        await callback.answer()
        mode_key = callback.data.replace("wedding_mode_", "")
        if mode_key not in WEDDING_MODES:
            await callback.message.answer("❌ Режим не найден.")
            return

        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state["mode"] = mode_key
        wedding_state[user_id] = state

        await callback.message.answer(
            WEDDING_CHOOSE_STYLE,
            parse_mode="HTML",
            reply_markup=wedding_styles_keyboard(),
        )

    @dp.callback_query(F.data.startswith("wedding_style_"))
    async def wedding_style(callback: CallbackQuery):
        await callback.answer()
        style_key = callback.data.replace("wedding_style_", "")
        if style_key not in WEDDING_STYLES:
            await callback.message.answer("❌ Стиль не найден.")
            return

        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state["style"] = style_key
        wedding_state[user_id] = state

        # Показать пример стиля
        mode = state.get("mode", "no_photo")
        mode_folder = WEDDING_MODES.get(mode, {}).get("example_folder", "no_photo")
        style_name = WEDDING_STYLES[style_key]["name"]

        await callback.message.answer(
            f"🎨 <b>Стиль: {style_name}</b>\n\n"
            "Вот пример — как выглядит открытка в этом стиле:",
            parse_mode="HTML",
        )
        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/holidays/wedding/{mode_folder}/{style_key}/example.jpg",
                caption=f"✨ {style_name}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"⚠️ Нет example.jpg для {mode_folder}/{style_key}: {e}")

        # Дальше — формат
        await callback.message.answer(
            WEDDING_CHOOSE_FORMAT,
            parse_mode="HTML",
            reply_markup=wedding_formats_keyboard(),
        )

    @dp.callback_query(F.data == "wedding_custom_style")
    async def wedding_custom_style(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        wedding_awaiting_custom[user_id] = "custom_style"
        await callback.message.answer(
            "✏️ <b>Свой стиль</b>\n\n"
            "Опиши, какой стиль хочешь. Можешь написать <b>любой</b> — "
            "от живописи до графики.\n\n"
            "<b>Примеры:</b>\n"
            "• «акварель с золотом»\n"
            "• «прованс, лаванда, кружево»\n"
            "• «чёрно-белая графика»\n"
            "• «стиль Тим Бёртон»\n"
            "• «как обложка Vogue»\n"
            "• «японская минималистичная живопись»\n\n"
            "Напиши свой вариант <b>одним сообщением</b>.",
            parse_mode="HTML",
        )

    @dp.callback_query(F.data == "wedding_back_style")
    async def wedding_back_style(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            WEDDING_CHOOSE_STYLE,
            parse_mode="HTML",
            reply_markup=wedding_styles_keyboard(),
        )

    @dp.callback_query(F.data.startswith("wedding_fmt_"))
    async def wedding_format(callback: CallbackQuery):
        await callback.answer()
        fmt_key = callback.data.replace("wedding_fmt_", "")
        if fmt_key not in WEDDING_FORMATS:
            await callback.message.answer("❌ Формат не найден.")
            return

        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state["format"] = fmt_key
        wedding_state[user_id] = state

        mode = state.get("mode", "no_photo")

        # Если «с фото» — просим фото, иначе генерим сразу
        if mode == "with_photo":
            await _show_upload(callback.message, state)
        else:
            await _generate_and_send(callback.message, user_id, state)

    @dp.callback_query(F.data == "wedding_back_format")
    async def wedding_back_format(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            WEDDING_CHOOSE_FORMAT,
            parse_mode="HTML",
            reply_markup=wedding_formats_keyboard(),
        )

    # ===== СВОДКА + ФОТО =====

    async def _show_upload(msg, state):
        mode = WEDDING_MODES.get(state.get("mode", ""), {})
        mode_name = mode.get("name", "—")
        style = WEDDING_STYLES.get(state.get("style", ""))
        style_name = style["name"] if style else state.get("custom_style", "—")
        fmt = WEDDING_FORMATS.get(state.get("format", ""))
        fmt_name = fmt["name"] if fmt else "—"

        caption = (
            "📋 <b>Твой выбор:</b>\n\n"
            f"💍 Режим: {mode_name}\n"
            f"🎨 Стиль: {style_name}\n"
            f"📐 Формат: {fmt_name}\n\n"
            f"{WEDDING_UPLOAD}"
        )
        await msg.answer(caption, parse_mode="HTML", reply_markup=wedding_upload_keyboard())

    @dp.callback_query(F.data == "wedding_upload")
    async def wedding_upload(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state["regen_done"] = False
        wedding_state[user_id] = state
        wedding_awaiting_photo.add(user_id)
        logger.info(f"✅ wedding_upload: user={user_id}")
        await callback.message.answer("📸 Жду фото. Пришли одно фото.")

    @dp.callback_query(F.data == "wedding_regen")
    async def wedding_regen(callback: CallbackQuery):
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        if not state.get("photo") and state.get("mode") == "with_photo":
            await callback.answer("❌ Нет фото. Загрузи заново.", show_alert=True)
            return
        if state.get("regen_done"):
            await callback.answer(
                "Перегенерация уже использована.",
                show_alert=True,
            )
            return
        state["regen_done"] = True
        wedding_state[user_id] = state
        await callback.answer("🎨 Генерирую другой вариант...")
        await _generate_and_send(callback.message, user_id, state)


# ===== ОБРАБОТКА СВОЕГО СТИЛЯ =====

async def handle_wedding_custom_text(message: Message, user_id: int, text: str) -> bool:
    """Если пользователь в режиме ввода своего стиля — сохраняет и идёт дальше."""
    step = wedding_awaiting_custom.get(user_id)
    if not step:
        return False

    text = text.strip()[:500]
    if not text:
        await message.answer("✏️ Пусто. Опиши стиль словами.")
        return True

    state = wedding_state.get(user_id, {})

    if step == "custom_style":
        state["style"] = "custom"
        state["custom_style"] = text
        wedding_state[user_id] = state
        wedding_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Стиль: <b>{text}</b>", parse_mode="HTML")
        await message.answer(
            WEDDING_CHOOSE_FORMAT,
            parse_mode="HTML",
            reply_markup=wedding_formats_keyboard(),
        )
        return True

    return False


# ===== ОБРАБОТКА ФОТО =====

async def handle_wedding_photo(message: Message, user_id: int, image_bytes: bytes):
    """Вызывается из main.py, когда пользователь в режиме wedding_awaiting_photo."""
    state = wedding_state.get(user_id, {})
    state["photo"] = image_bytes
    state["regen_done"] = False
    wedding_state[user_id] = state
    wedding_awaiting_photo.discard(user_id)
    await message.answer("✅ Фото получено!")
    await _generate_and_send(message, user_id, state)


# ===== ГЕНЕРАЦИЯ =====

def _build_prompt(state: dict) -> str | None:
    mode = state.get("mode")
    style_key = state.get("style")
    custom_style = state.get("custom_style", "")

    if not mode or not style_key:
        return None

    # Стиль
    if style_key == "custom" and custom_style:
        style_lock = (
            f"СТИЛЬ: {custom_style}. "
            "Всё изображение (фон, декор, люди) — в этом едином стиле. "
        )
    else:
        style = WEDDING_STYLES.get(style_key)
        if not style:
            return None
        style_lock = style["prompt"] + " "

    # Общие правила по людям (если есть фото)
    face_lock = ""
    if mode == "with_photo":
        face_lock = (
            "ЛЮДИ: посчитай ТОЧНО, сколько людей на исходном фото. "
            "На новой картинке — РОВНО СТОЛЬКО ЖЕ. "
            "НЕ добавляй никого. НЕ убирай никого. НЕ заменяй. "
            "Сохрани у каждого человека черты лица, причёску, цвет волос, пол, возраст — "
            "но В ЕДИНОМ ХУДОЖЕСТВЕННОМ СТИЛЕ открытки. "
            "НЕ фотореализм, а нарисованные/стилизованные узнаваемые лица. "
            "Лица — часть общей композиции, а не аппликация. "
        )

    # Свадебная атмосфера
    wedding_lock = (
        "АТМОСФЕРА: свадебная, романтичная, тёплая. "
        "Ощущение праздника, нежности, любви. "
        "Мягкий свет, лёгкое свечение, элегантность. "
    )

    # Место под подпись — только для открыток без фото
    if mode in ("no_photo", "no_photo_car"):
        sign_lock = (
            "МЕСТО ПОД ПОДПИСЬ: в нижней части открытки оставь "
            "чистую светлую зону под ручную подпись. "
            "Внутри зоны — НИКАКОГО текста, только ровный фон. "
            "Зона может быть обрамлена декоративной линией или рамкой. "
        )
    else:
        sign_lock = ""

    # Ретро-авто
    car_lock = ""
    if mode == "no_photo_car":
        custom_car = state.get("custom_car", "")
        if custom_car:
            car_lock = (
                f"В КАДРЕ — ВИНТАЖНЫЙ АВТОМОБИЛЬ: {custom_car}. "
                "Автомобиль украшен свадебно: цветы, ленты, венки. "
                "Автомобиль — часть композиции, элегантный, красивый. "
                "НЕ современная машина. Только ретро/классика. "
            )
        else:
            car_lock = (
                "В КАДРЕ — ВИНТАЖНЫЙ АВТОМОБИЛЬ (ретро 1950–1970-х). "
                "Украшен свадебно: цветы, ленты, венки. "
                "Автомобиль — часть композиции, элегантный, красивый. "
                "НЕ современная машина. Только ретро/классика. "
            )

    # Формат
    from main import get_size_for_format
    fmt_key = state.get("format", "1_1")
    fmt = WEDDING_FORMATS.get(fmt_key, WEDDING_FORMATS["1_1"])
    photo_bytes = state.get("photo")
    img_size = get_size_for_format(fmt_key, photo_bytes)

    format_lock = (
        f"ФОРМАТ КАДРА: {fmt['name']}, размер {img_size}. "
        f"Построй КРАСИВУЮ ГАРМОНИЧНУЮ композицию под этот формат — {fmt['desc']}. "
        f"Верни изображение РОВНО {img_size} пикселей. "
    )

    full = (
        f"Свадебная открытка. "
        f"{style_lock}"
        f"{face_lock}"
        f"{wedding_lock}"
        f"{sign_lock}"
        f"{car_lock}"
        f"{format_lock}"
        "Финальный стиль: единая художественная стилизация — "
        "фон, декор и люди в одном ключе. НЕ фотореализм. "
        "Изображение цельное, гармоничное, элегантное."
    )
    return full


async def _generate_and_send(message: Message, user_id: int, state: dict):
    from ai_service import generate_image, generate_image_from_text
    from main import get_balance, spend_generation, test_mode, buy_generations_keyboard

    mode = state.get("mode")

    # Для режима с фото — обязательна фотография
    if mode == "with_photo" and not state.get("photo"):
        await message.answer("❌ Нет фото. Загрузи заново.")
        return

    is_regen = state.get("regen_done", False)

    if not is_regen:
        if not spend_generation(user_id):
            await message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard(),
            )
            return

    full_prompt = _build_prompt(state)
    if not full_prompt:
        await message.answer("❌ Не все параметры выбраны. Начни заново: /start")
        return

    await message.answer("🎨 Генерирую открытку... Обычно это занимает до минуты.")

    logger.info(f"🎨 wedding генерация: user={user_id}, mode={mode}, regen={is_regen}")

    try:
        if mode == "with_photo":
            img = generate_image(state.get("photo"), full_prompt)
        else:
            img = generate_image_from_text(full_prompt)
        if not img:
            logger.warning("⚠️ wedding: первая попытка не удалась, пробую ещё раз")
            await message.answer("🔄 Сервис задумался, пробую ещё раз...")
            if mode == "with_photo":
                img = generate_image(state.get("photo"), full_prompt)
            else:
                img = generate_image_from_text(full_prompt)
    except Exception as e:
        logger.exception(f"❌ wedding: исключение при генерации: {e}")
        img = None

    if not img:
        logger.warning(f"❌ wedding: генерация вернула None")
        state["regen_done"] = False
        wedding_state[user_id] = state
        await message.answer(
            "😔 Не удалось сгенерировать открытку.\n\n"
            "✅ Попытка НЕ списана.\n"
            "🔄 Попробуй ещё раз."
        )
        return

    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    try:
        await message.answer_photo(
            BufferedInputFile(img, filename="wedding.jpg"),
            caption=f"💍 <b>Готово!</b>\n\n💎 Баланс: {balance_text}",
            parse_mode="HTML",
            reply_markup=wedding_result_keyboard(),
        )
    except Exception as e:
        logger.exception(f"❌ wedding: ошибка отправки фото: {e}")
        await message.answer("❌ Не удалось отправить фото.")
