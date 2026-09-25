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

import requests as _requests


def _fetch_image(url: str) -> bytes | None:
    """Скачивает картинку с URL. Возвращает bytes или None."""
    try:
        r = _requests.get(url, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as e:
        logger.warning(f"⚠️ Не удалось скачать {url}: {e}")
    return None


BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main/examples"

# ===== РЕЖИМЫ =====

WEDDING_MODES = {
    "no_photo": {
        "name": "💌 Открытка без фото",
        "short": "💌 Открытка без фото",
        "desc": (
            "Готовая свадебная открытка. Без фото. "
            "Заголовок «Наша свадьба», место под имена, дату и приглашение."
        ),
        "with_photo": False,
        "with_car": False,
        "example_folder": "no_photo",
    },
    "no_photo_car": {
        "name": "🚗 Открытка с ретро-авто",
        "short": "🚗 С ретро-авто",
        "desc": (
            "Свадебная открытка с винтажным автомобилем. Без фото. "
            "Машина с цветами и лентами, место под имена и приглашение."
        ),
        "with_photo": False,
        "with_car": True,
        "example_folder": "no_photo_car",
    },
    "with_photo": {
        "name": "📸 Пригласительное с фото",
        "short": "📸 С фото",
        "desc": (
            "Пригласительное с вашим фото. Лица сохраняются, "
            "стиль — как у открытки. Заголовок, имена, дата."
        ),
        "with_photo": True,
        "with_car": False,
        "example_folder": "with_photo",
    },
    "with_photo_car": {
        "name": "🚗📸 С ретро-авто и фото",
        "short": "🚗📸 С авто и фото",
        "desc": (
            "Пара вместе с винтажным автомобилем. Свободный ракурс: "
            "рядом, на капоте, в кабриолете. Лица сохраняются."
        ),
        "with_photo": True,
        "with_car": True,
        "example_folder": "with_photo_car",
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
    "1_1": {"name": "📱 1:1 (квадрат)", "short": "📱 1:1", "desc": "квадратная композиция"},
    "3_4": {"name": "📱 3:4 (вертикаль)", "short": "📱 3:4", "desc": "вертикальная композиция"},
    "4_3": {"name": "🖼 4:3 (горизонт)", "short": "🖼 4:3", "desc": "горизонтальная композиция"},
    "4_5": {"name": "📱 4:5 (Instagram)", "short": "📱 4:5", "desc": "вертикаль для Instagram"},
    "9_16": {"name": "📱 9:16 (сторис)", "short": "📱 9:16", "desc": "полная вертикаль для сторис"},
    "16_9": {"name": "🖼 16:9 (панорама)", "short": "🖼 16:9", "desc": "панорамная горизонталь"},
}

# ===== СОСТОЯНИЕ =====

wedding_state = {}
wedding_awaiting_photo = set()
wedding_awaiting_names = set()
wedding_awaiting_date = set()
wedding_awaiting_custom = {}


def reset_wedding_state(user_id: int):
    wedding_state.pop(user_id, None)
    wedding_awaiting_photo.discard(user_id)
    wedding_awaiting_names.discard(user_id)
    wedding_awaiting_date.discard(user_id)
    wedding_awaiting_custom.pop(user_id, None)


def is_user_in_wedding_flow(user_id: int) -> bool:
    return (
        user_id in wedding_state
        and user_id not in wedding_awaiting_photo
        and user_id not in wedding_awaiting_names
        and user_id not in wedding_awaiting_date
    )


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
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_mode")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_options_keyboard(state: dict):
    """Клавиатура доп. опций: имена, дата, фото."""
    rows = []

    names = state.get("names", "")
    if names:
        rows.append([InlineKeyboardButton(
            text=f"✏️ Имена: {names}",
            callback_data="wedding_edit_names",
        )])
        rows.append([InlineKeyboardButton(
            text="🗑 Убрать имена",
            callback_data="wedding_remove_names",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="✏️ Добавить имена",
            callback_data="wedding_add_names",
        )])

    date = state.get("date", "")
    if date:
        rows.append([InlineKeyboardButton(
            text=f"📅 Дата: {date}",
            callback_data="wedding_edit_date",
        )])
        rows.append([InlineKeyboardButton(
            text="🗑 Убрать дату",
            callback_data="wedding_remove_date",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="📅 Добавить дату",
            callback_data="wedding_add_date",
        )])

    mode = state.get("mode", "")
    mode_info = WEDDING_MODES.get(mode, {})
    if mode_info.get("with_photo"):
        rows.append([InlineKeyboardButton(
            text="📸 Загрузить фото",
            callback_data="wedding_upload",
        )])

    rows.append([InlineKeyboardButton(
        text="➡️ Дальше — выбрать формат",
        callback_data="wedding_to_format",
    )])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_style")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_formats_keyboard():
    rows = []
    for key, fmt in WEDDING_FORMATS.items():
        rows.append([InlineKeyboardButton(text=fmt["short"], callback_data=f"wedding_fmt_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_options")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wedding_upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="wedding_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="wedding_back_options")],
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
    "<b>Что можно сделать:</b>\n\n"
    "💌 <b>Открытка без фото</b> — готовая свадебная открытка "
    "с заголовком «Наша свадьба» и местом под имена, дату и приглашение. "
    "Распечатай и впиши от руки (или укажи имена в боте — ИИ попробует их нарисовать).\n\n"
    "🚗 <b>Открытка с ретро-авто</b> — то же, но с винтажным автомобилем, "
    "цветами и лентами. Ретро 1950–1970-х, красиво и стильно.\n\n"
    "📸 <b>Пригласительное с фото</b> — пригласительное с вашим фото. "
    "Лица сохраняются в едином художественном стиле.\n\n"
    "🚗📸 <b>С ретро-авто и фото</b> — пара вместе с машиной. "
    "Свободный ракурс: рядом, на капоте, в кабриолете.\n\n"
    "Выбери, что хочешь создать:"
)

WEDDING_CHOOSE_STYLE = (
    "🎨 <b>Шаг 1 из 3. Выбери стиль оформления</b>\n\n"
    "Стиль влияет на всё: фон, декор, людей, автомобиль. "
    "Всё изображение будет в едином ключе.\n\n"
    "• 🌿 Ботаника — эвкалипт, оливы, сухоцветы\n"
    "• 🎨 Акварель — мягкая живопись, пастель\n"
    "• ⬜ Минимализм — графика, много воздуха\n"
    "• ✨ Арт-деко — геометрия, золото, гламур\n"
    "• 📜 Винтаж — сепия, кружево, романтика\n\n"
    "Или напиши свой стиль."
)

WEDDING_OPTIONS_TEXT = (
    "📝 <b>Шаг 2 из 3. Дополнительные опции</b>\n\n"
    "Тут можно добавить то, что нужно:\n\n"
    "✏️ <b>Имена</b> — впиши имена жениха и невесты, например "
    "«Степан и Елена». ИИ попробует их нарисовать на открытке. "
    "Если не добавлять — останется пустое место под ручную подпись.\n\n"
    "📅 <b>Дата</b> — впиши дату свадьбы, например «12 июля 2026». "
    "Тоже можно оставить пустым — впишешь от руки.\n\n"
    "📸 <b>Фото</b> — если режим с фото, загрузи фотографию, "
    "откуда взять лица.\n\n"
    "Выбери, что добавить, или жми «➡️ Дальше — выбрать формат»:"
)

WEDDING_CHOOSE_FORMAT = (
    "📐 <b>Шаг 3 из 3. Выбери формат кадра</b>\n\n"
    "• 📱 1:1 — квадрат, универсально\n"
    "• 📱 3:4 — вертикаль, для печати\n"
    "• 🖼 4:3 — горизонт, классика\n"
    "• 📱 4:5 — вертикаль для Instagram\n"
    "• 📱 9:16 — сторис, узкий конверт\n"
    "• 🖼 16:9 — панорама, разворот открытки"
)

WEDDING_UPLOAD = (
    "📸 <b>Пришли фото</b>\n\n"
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

        intro_bytes = _fetch_image(f"{BASE}/holidays/wedding/intro.jpg")
        if intro_bytes:
            try:
                await callback.message.answer_photo(
                    BufferedInputFile(intro_bytes, filename="intro.jpg"),
                    caption=WEDDING_INTRO,
                    parse_mode="HTML",
                    reply_markup=wedding_intro_keyboard(),
                )
                return
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки intro: {e}")

        await callback.message.answer(
            WEDDING_INTRO,
            parse_mode="HTML",
            reply_markup=wedding_intro_keyboard(),
        )

    @dp.callback_query(F.data == "wedding_back_mode")
    async def wedding_back_mode(callback: CallbackQuery):
        await callback.answer()
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

        mode = state.get("mode", "no_photo")
        mode_folder = WEDDING_MODES.get(mode, {}).get("example_folder", "no_photo")
        style_name = WEDDING_STYLES[style_key]["name"]

        await callback.message.answer(
            f"🎨 <b>Стиль: {style_name}</b>\n\n"
            "Вот пример — как выглядит открытка в этом стиле:",
            parse_mode="HTML",
        )
        before_bytes = _fetch_image(f"{BASE}/holidays/wedding/{mode_folder}/{style_key}/before.jpg")
        if before_bytes:
            try:
                await callback.message.answer_photo(
                    BufferedInputFile(before_bytes, filename="before.jpg"),
                    caption="📷 <b>ДО</b> — обычное фото",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки before.jpg: {e}")

        after_bytes = _fetch_image(f"{BASE}/holidays/wedding/{mode_folder}/{style_key}/after.jpg")
        if after_bytes:
            try:
                await callback.message.answer_photo(
                    BufferedInputFile(after_bytes, filename="after.jpg"),
                    caption=f"✨ <b>ПОСЛЕ</b> — {style_name}",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки after.jpg: {e}")

        # Дальше — доп. опции
        await callback.message.answer(
            WEDDING_OPTIONS_TEXT,
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
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

    # ===== ДОП. ОПЦИИ =====

    @dp.callback_query(F.data == "wedding_back_options")
    async def wedding_back_options(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        await callback.message.answer(
            WEDDING_OPTIONS_TEXT,
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
        )

    @dp.callback_query(F.data.in_({"wedding_add_names", "wedding_edit_names"}))
    async def wedding_add_names(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        wedding_awaiting_names.add(user_id)
        await callback.message.answer(
            "✏️ <b>Имена</b>\n\n"
            "Напиши имена <b>одним сообщением</b>.\n\n"
            "<b>Примеры:</b>\n"
            "• Степан и Елена\n"
            "• Анна & Михаил\n\n"
            "⚠️ ИИ попробует нарисовать их на открытке. "
            "Может получиться неточно. Если хочешь идеально — "
            "оставь имена пустыми и впиши их от руки после печати.",
        )

    @dp.callback_query(F.data == "wedding_remove_names")
    async def wedding_remove_names(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state.pop("names", None)
        wedding_state[user_id] = state
        await callback.message.answer(
            "🗑 Имена убраны.",
            reply_markup=wedding_options_keyboard(state),
        )

    @dp.callback_query(F.data.in_({"wedding_add_date", "wedding_edit_date"}))
    async def wedding_add_date(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        wedding_awaiting_date.add(user_id)
        await callback.message.answer(
            "📅 <b>Дата свадьбы</b>\n\n"
            "Напиши дату <b>одним сообщением</b>.\n\n"
            "<b>Примеры:</b>\n"
            "• 12 июля 2026\n"
            "• 12.07.2026\n"
            "• Лето 2026\n\n"
            "⚠️ ИИ попробует нарисовать её на открытке. "
            "Может получиться неточно. Если хочешь идеально — "
            "оставь дату пустой и впиши её от руки после печати.",
        )

    @dp.callback_query(F.data == "wedding_remove_date")
    async def wedding_remove_date(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        state.pop("date", None)
        wedding_state[user_id] = state
        await callback.message.answer(
            "🗑 Дата убрана.",
            reply_markup=wedding_options_keyboard(state),
        )

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

    @dp.callback_query(F.data == "wedding_to_format")
    async def wedding_to_format(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        mode = state.get("mode", "")
        mode_info = WEDDING_MODES.get(mode, {})

        if mode_info.get("with_photo") and not state.get("photo"):
            await callback.message.answer(
                "⚠️ <b>Сначала загрузи фото</b>\n\n"
                "Ты выбрал режим с фотографией. "
                "Нажми «📸 Загрузить фото» — и потом продолжишь.",
                parse_mode="HTML",
                reply_markup=wedding_options_keyboard(state),
            )
            return

        await callback.message.answer(
            WEDDING_CHOOSE_FORMAT,
            parse_mode="HTML",
            reply_markup=wedding_formats_keyboard(),
        )

    # ===== ФОРМАТ =====

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

        await _generate_and_send(callback.message, user_id, state)

    @dp.callback_query(F.data == "wedding_back_format")
    async def wedding_back_format(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        await callback.message.answer(
            WEDDING_OPTIONS_TEXT,
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
        )

    # ===== ПЕРЕГЕНЕРАЦИЯ =====

    @dp.callback_query(F.data == "wedding_regen")
    async def wedding_regen(callback: CallbackQuery):
        user_id = callback.from_user.id
        state = wedding_state.get(user_id, {})
        mode_info = WEDDING_MODES.get(state.get("mode", ""), {})
        if mode_info.get("with_photo") and not state.get("photo"):
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


# ===== ОБРАБОТКА СВОЕГО СТИЛЯ / ИМЁН / ДАТЫ =====

async def handle_wedding_custom_text(message: Message, user_id: int, text: str) -> bool:
    """Обрабатывает ввод стиля, имён и даты."""
    text = text.strip()[:200]
    if not text:
        return False

    # Свой стиль
    step = wedding_awaiting_custom.get(user_id)
    if step == "custom_style":
        state = wedding_state.get(user_id, {})
        state["style"] = "custom"
        state["custom_style"] = text
        wedding_state[user_id] = state
        wedding_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Стиль: <b>{text}</b>", parse_mode="HTML")
        await message.answer(
            WEDDING_OPTIONS_TEXT,
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
        )
        return True

    # Имена
    if user_id in wedding_awaiting_names:
        wedding_awaiting_names.discard(user_id)
        state = wedding_state.get(user_id, {})
        state["names"] = text
        wedding_state[user_id] = state
        await message.answer(
            f"✅ Имена: <b>{text}</b>\n\n"
            "ИИ попробует их нарисовать.",
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
        )
        return True

    # Дата
    if user_id in wedding_awaiting_date:
        wedding_awaiting_date.discard(user_id)
        state = wedding_state.get(user_id, {})
        state["date"] = text
        wedding_state[user_id] = state
        await message.answer(
            f"✅ Дата: <b>{text}</b>",
            parse_mode="HTML",
            reply_markup=wedding_options_keyboard(state),
        )
        return True

    return False


# ===== ОБРАБОТКА ФОТО =====

async def handle_wedding_photo(message: Message, user_id: int, image_bytes: bytes):
    state = wedding_state.get(user_id, {})
    state["photo"] = image_bytes
    state["regen_done"] = False
    wedding_state[user_id] = state
    wedding_awaiting_photo.discard(user_id)
    await message.answer("✅ Фото получено!")
    await message.answer(
        WEDDING_OPTIONS_TEXT,
        parse_mode="HTML",
        reply_markup=wedding_options_keyboard(state),
    )


# ===== ГЕНЕРАЦИЯ =====

def _build_prompt(state: dict) -> str | None:
    mode = state.get("mode")
    style_key = state.get("style")
    custom_style = state.get("custom_style", "")

    if not mode or not style_key:
        return None

    mode_info = WEDDING_MODES.get(mode, {})
    with_photo = mode_info.get("with_photo", False)
    with_car = mode_info.get("with_car", False)

    # Стиль
    if style_key == "custom" and custom_style:
        style_lock = (
            f"СТИЛЬ: {custom_style}. "
            "Всё изображение (фон, декор, люди, авто) — в этом едином стиле. "
        )
    else:
        style = WEDDING_STYLES.get(style_key)
        if not style:
            return None
        style_lock = style["prompt"] + " "

    # Люди — если фото
    face_lock = ""
    if with_photo:
        face_lock = (
            "ЛЮДИ: посчитай ТОЧНО, сколько людей на исходном фото. "
            "На новой картинке — РОВНО СТОЛЬКО ЖЕ. "
            "НЕ добавляй никого. НЕ убирай никого. НЕ заменяй. "
            "Сохрани у каждого человека черты лица, причёску, цвет волос, пол, возраст — "
            "но В ЕДИНОМ ХУДОЖЕСТВЕННОМ СТИЛЕ открытки. "
            "НЕ фотореализм, а нарисованные/стилизованные узнаваемые лица. "
            "Лица — часть общей композиции, а не аппликация. "
        )

    # Запрет людей — если без фото
    no_people_lock = ""
    if not with_photo:
        no_people_lock = (
            "КАТЕГОРИЧЕСКИ БЕЗ ЛЮДЕЙ. "
            "В кадре НЕТ ни одного человека: ни жениха, ни невесты, ни пары, ни ребёнка, "
            "ни силуэта, ни фигуры, ни лица, ни рук, ни ног, ни тени человека. "
            "Никаких людей на заднем плане, в отражениях, в окнах. "
            "Только фон, декор, цветы, ленты, предметы "
            "и (если есть авто) сам автомобиль БЕЗ пассажиров. "
        )

    # Свадебная атмосфера
    wedding_lock = (
        "АТМОСФЕРА: свадебная, романтичная, тёплая. "
        "Ощущение праздника, нежности, любви. "
        "Мягкий свет, лёгкое свечение, элегантность. "
    )

    # Заголовок «Наша свадьба»
    title_lock = (
        "ЗАГОЛОВОК: в верхней или нижней части открытки — крупный "
        "декоративный рукописный заголовок «Наша свадьба». "
        "Золотой или в цвет стиля. Каллиграфия. "
        "Это ЕДИНСТВЕННЫЙ обязательный текст на открытке. "
    )

    # Имена
    names = state.get("names", "").strip()
    if names:
        names_lock = (
            f"ИМЕНА: под заголовком напиши рукописным шрифтом имена: «{names}». "
            "Крупно, разборчиво, декоративно. "
        )
    else:
        names_lock = (
            "ИМЕНА: НЕ пиши никаких имён. "
            "Под заголовком оставь ЧИСТУЮ декоративную зону под ручную подпись — "
            "например, декоративная линия или лента. "
            "Внутри зоны — никакого текста. "
        )

    # Дата
    date = state.get("date", "").strip()
    if date:
        date_lock = (
            f"ДАТА: под именами напиши рукописным шрифтом дату: «{date}». "
        )
    else:
        date_lock = (
            "ДАТА: НЕ пиши дату. "
            "Оставь место под дату — короткая декоративная линия. "
        )

    # Место под приглашение — всегда
    invite_lock = (
        "ПРИГЛАШЕНИЕ: в нижней части открытки оставь ШИРОКУЮ ЧИСТУЮ зону "
        "под ручную подпись приглашения — например, декоративная рамка "
        "или линия. Внутри зоны — никакого текста. "
        "Сюда пользователь впишет от руки, кого он приглашает. "
    )

    # Авто
    car_lock = ""
    if with_car:
        custom_car = state.get("custom_car", "")
        if custom_car:
            car_lock = (
                f"РЕТРО-АВТОМОБИЛЬ: {custom_car}. "
                "Автомобиль в кадре, украшен свадебно: цветы, ленты, венки. "
                "Элегантный, красивый, часть композиции. "
                "Только ретро/классика, НЕ современная машина. "
            )
        else:
            car_lock = (
                "РЕТРО-АВТОМОБИЛЬ: винтажный автомобиль 1950–1970-х. "
                "Украшен свадебно: цветы, ленты, венки. "
                "Элегантный, красивый, часть композиции. "
                "Только ретро/классика, НЕ современная машина. "
            )

    if with_photo and with_car:
        car_lock += (
            "ПАРА И АВТО: люди с фото и автомобиль вместе. "
            "Ракурс свободный: рядом с машиной, на капоте, "
            "в кабриолете, облокотились. Как красиво смотрится. "
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
        f"{no_people_lock}"
        f"{wedding_lock}"
        f"{title_lock}"
        f"{names_lock}"
        f"{date_lock}"
        f"{invite_lock}"
        f"{car_lock}"
        f"{format_lock}"
        "Финальный стиль: единая художественная стилизация — "
        "фон, декор и люди в одном ключе. НЕ фотореализм. "
        "Изображение цельное, гармоничное, элегантное. "
        "НИКАКОГО лишнего текста, кроме указанного выше."
    )
    return full


async def _generate_and_send(message: Message, user_id: int, state: dict):
    from ai_service import generate_image, generate_image_from_text
    from main import get_balance, spend_generation, test_mode, buy_generations_keyboard

    mode_info = WEDDING_MODES.get(state.get("mode", ""), {})
    with_photo = mode_info.get("with_photo", False)

    if with_photo and not state.get("photo"):
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

    logger.info(f"🎨 wedding генерация: user={user_id}, mode={state.get('mode')}, regen={is_regen}")

    try:
        if with_photo:
            img = generate_image(state.get("photo"), full_prompt)
        else:
            img = generate_image_from_text(full_prompt)
        if not img:
            logger.warning("⚠️ wedding: первая попытка не удалась, пробую ещё раз")
            await message.answer("🔄 Сервис задумался, пробую ещё раз...")
            if with_photo:
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
