"""
Создание изображения по описанию или по фото + описанию.
Логика как в других инструментах, со своими состояниями.
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
    try:
        r = _requests.get(url, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as e:
        logger.warning(f"⚠️ Не удалось скачать {url}: {e}")
    return None


BASE_PI = "https://raw.githubusercontent.com/photorazbor/photo-bot/main/examples"

# ===== ФОРМАТЫ =====
PROMPT_FORMATS = {
    "1_1": {"name": "📱 1:1 (квадрат)", "short": "📱 1:1", "desc": "квадратная композиция"},
    "3_4": {"name": "📱 3:4 (вертикаль)", "short": "📱 3:4", "desc": "вертикальная композиция"},
    "4_3": {"name": "🖼 4:3 (горизонт)", "short": "🖼 4:3", "desc": "горизонтальная композиция"},
    "9_16": {"name": "📱 9:16 (сторис)", "short": "📱 9:16", "desc": "полная вертикаль для сторис"},
    "16_9": {"name": "🖼 16:9 (панорама)", "short": "🖼 16:9", "desc": "панорамная горизонталь"},
}

# ===== СОСТОЯНИЕ =====

prompt_state = {}                 # {user_id: {"mode": ..., "prompt": ..., "photo": bytes, "format": ...}}
prompt_awaiting_photo = set()     # user_id, ждущие фото
prompt_awaiting_text = set()      # user_id, ждущие текст промпта


def reset_prompt_state(user_id: int):
    prompt_state.pop(user_id, None)
    prompt_awaiting_photo.discard(user_id)
    prompt_awaiting_text.discard(user_id)


def is_user_in_prompt_flow(user_id: int) -> bool:
    return (
        user_id in prompt_state
        or user_id in prompt_awaiting_photo
        or user_id in prompt_awaiting_text
    )


# ===== КЛАВИАТУРЫ =====

def prompt_intro_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 По описанию", callback_data="prompt_mode_text")],
        [InlineKeyboardButton(text="🖼 По фото", callback_data="prompt_mode_photo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="tools_menu")],
    ])


def prompt_formats_keyboard():
    rows = []
    for key, fmt in PROMPT_FORMATS.items():
        rows.append([InlineKeyboardButton(text=fmt["short"], callback_data=f"prompt_fmt_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="prompt_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prompt_result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data="prompt_regen")],
        [InlineKeyboardButton(text="🎨 Создать ещё", callback_data="prompt_start")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

PROMPT_INTRO = (
    "🎨 <b>Создание изображения</b>\n\n"
    "Можешь создать картинку двумя способами.\n\n"
    "📝 <b>По описанию</b>\n"
    "Просто опиши словами, что хочешь увидеть. ИИ нарисует с нуля.\n"
    "<i>Пример: «Зимний лес на рассвете, туман, тёплый свет, "
    "кинематографично»</i>\n\n"
    "🖼 <b>По фото</b>\n"
    "Приложи одно своё фото и опиши, что с ним сделать. "
    "ИИ сохранит основу и воплотит твою идею.\n"
    "<i>Пример: «Сделай портрет в акварельном стиле»\n"
    "«Помести меня в этот пейзаж»\n"
    "«Стилизуй под ретро 60-х»</i>\n\n"
    "💰 <b>Стоимость:</b> 1 генерация с баланса\n\n"
    "⚙️ <i>Работает на модели Gemini 3.1 Flash Image "
    "(Nano Banana 2) от Google</i>\n\n"
    "Выбери способ:"
)

PROMPT_TEXT_INSTRUCTION = (
    "📝 <b>По описанию</b>\n\n"
    "Опиши словами, что хочешь увидеть. Одним сообщением.\n\n"
    "Чем детальнее — тем точнее результат. Можно указать:\n"
    "• Что в кадре (сюжет)\n"
    "• Стиль (реализм, акварель, киберпанк)\n"
    "• Свет и настроение (тёплый, вечерний, кинематографично)\n"
    "• Детали (снег, туман, блики)\n\n"
    "<i>Например: «Портрет девушки в весеннем саду, "
    "мягкий свет, цветы вишни, акварельный стиль»</i>\n\n"
    "Напиши своё описание 👇"
)

PROMPT_PHOTO_INSTRUCTION = (
    "🖼 <b>По фото</b>\n\n"
    "📸 <b>Шаг 1.</b> Пришли одно своё фото.\n\n"
    "Требования:\n"
    "• По грудь, по пояс или по колено\n"
    "• Лицо крупное, чёткое, без сильных теней\n"
    "• Хорошее освещение\n\n"
    "После фото — попросишь, что с ним сделать."
)

PROMPT_PHOTO_TEXT_INSTRUCTION = (
    "✅ <b>Фото получено.</b>\n\n"
    "✏️ <b>Шаг 2.</b> Опиши, что сделать с фото. Одним сообщением.\n\n"
    "<i>Например:</i>\n"
    "• «Сделай портрет в акварельном стиле»\n"
    "• «Помести меня в заснеженный лес»\n"
    "• «Стилизуй под ретро 60-х»\n"
    "• «Сделай кинематографичный кадр»\n\n"
    "Напиши описание 👇"
)

PROMPT_CHOOSE_FORMAT = (
    "📐 <b>Шаг 3.</b> Выбери формат кадра:\n\n"
    "• 📱 1:1 — квадрат, универсально\n"
    "• 📱 3:4 — вертикаль\n"
    "• 🖼 4:3 — горизонт\n"
    "• 📱 9:16 — сторис\n"
    "• 🖼 16:9 — панорама"
)


# ===== РЕГИСТРАЦИЯ =====

def register_prompt_handlers(dp):
    """Регистрирует обработчики «Создание изображения»."""

    @dp.callback_query(F.data == "prompt_start")
    async def prompt_start(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        reset_prompt_state(user_id)

        # Показать примеры (если залиты)
        for name in ("example_text", "example_photo"):
            img = _fetch_image(f"{BASE_PI}/prompt/{name}.jpg")
            if not img:
                continue
            try:
                caption = (
                    "📝 Пример: <b>по описанию</b>"
                    if name == "example_text"
                    else "🖼 Пример: <b>по фото + описание</b>"
                )
                await callback.message.answer_photo(
                    BufferedInputFile(img, filename=f"{name}.jpg"),
                    caption=caption,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка отправки {name}: {e}")

        await callback.message.answer(
            PROMPT_INTRO,
            parse_mode="HTML",
            reply_markup=prompt_intro_keyboard(),
        )

    @dp.callback_query(F.data == "prompt_mode_text")
    async def prompt_mode_text(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = prompt_state.get(user_id, {})
        state["mode"] = "text"
        prompt_state[user_id] = state
        prompt_awaiting_text.add(user_id)
        await callback.message.answer(
            PROMPT_TEXT_INSTRUCTION,
            parse_mode="HTML",
        )

    @dp.callback_query(F.data == "prompt_mode_photo")
    async def prompt_mode_photo(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = prompt_state.get(user_id, {})
        state["mode"] = "photo"
        prompt_state[user_id] = state
        prompt_awaiting_photo.add(user_id)
        await callback.message.answer(
            PROMPT_PHOTO_INSTRUCTION,
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("prompt_fmt_"))
    async def prompt_format(callback: CallbackQuery):
        await callback.answer()
        fmt_key = callback.data.replace("prompt_fmt_", "")
        if fmt_key not in PROMPT_FORMATS:
            await callback.message.answer("❌ Формат не найден.")
            return

        user_id = callback.from_user.id
        state = prompt_state.get(user_id, {})
        state["format"] = fmt_key
        prompt_state[user_id] = state

        await _generate_and_send(callback.message, user_id, state)

    @dp.callback_query(F.data == "prompt_regen")
    async def prompt_regen(callback: CallbackQuery):
        user_id = callback.from_user.id
        state = prompt_state.get(user_id, {})
        if not state.get("prompt"):
            await callback.answer("❌ Нет промпта. Начни заново.", show_alert=True)
            return
        if state.get("regen_done"):
            await callback.answer(
                "Перегенерация уже использована.",
                show_alert=True,
            )
            return
        state["regen_done"] = True
        prompt_state[user_id] = state
        await callback.answer("🎨 Генерирую другой вариант...")
        await _generate_and_send(callback.message, user_id, state, is_regen=True)


# ===== ОБРАБОТКА ТЕКСТА =====

async def handle_prompt_text(message: Message, user_id: int, text: str) -> bool:
    """Обрабатывает ввод промпта."""
    if user_id not in prompt_awaiting_text:
        return False

    text = text.strip()[:800]
    if not text:
        await message.answer("✏️ Пусто. Опиши словами.")
        return True

    prompt_awaiting_text.discard(user_id)
    state = prompt_state.get(user_id, {})
    state["prompt"] = text
    state["regen_done"] = False
    prompt_state[user_id] = state

    await message.answer(
        f"✅ Описание принято.\n\n{PROMPT_CHOOSE_FORMAT}",
        parse_mode="HTML",
        reply_markup=prompt_formats_keyboard(),
    )
    return True


# ===== ОБРАБОТКА ФОТО =====

async def handle_prompt_photo(message: Message, user_id: int, image_bytes: bytes) -> bool:
    """Принимает фото в режиме «По фото», затем ждёт промпт."""
    if user_id not in prompt_awaiting_photo:
        return False

    prompt_awaiting_photo.discard(user_id)
    state = prompt_state.get(user_id, {})
    state["photo"] = image_bytes
    prompt_state[user_id] = state
    prompt_awaiting_text.add(user_id)

    await message.answer(
        PROMPT_PHOTO_TEXT_INSTRUCTION,
        parse_mode="HTML",
    )
    return True


# ===== ГЕНЕРАЦИЯ =====

async def _generate_and_send(message: Message, user_id: int, state: dict, is_regen: bool = False):
    from ai_service import generate_image, generate_image_from_text
    from main import get_balance, spend_generation, test_mode, buy_generations_keyboard, get_size_for_format

    prompt_text = state.get("prompt", "").strip()
    if not prompt_text:
        await message.answer("❌ Нет описания. Начни заново: /start")
        return

    mode = state.get("mode", "text")
    photo = state.get("photo")
    fmt_key = state.get("format", "1_1")
    fmt = PROMPT_FORMATS.get(fmt_key, PROMPT_FORMATS["1_1"])

    # Размер под формат
    img_size = get_size_for_format(fmt_key, photo if photo else None)

    # Финальный промпт
    if mode == "photo" and photo:
        final_prompt = (
            f"{prompt_text}. "
            f"Сохрани всех людей с исходного фото — их лица, черты, "
            f"причёску, одежду в точности. "
            f"НЕ добавляй новых людей. НЕ убирай никого. "
            f"Формат: {fmt['name']}, размер {img_size}. "
            f"Верни изображение РОВНО {img_size} пикселей."
        )
    else:
        final_prompt = (
            f"{prompt_text}. "
            f"Высокое качество, детализированно, профессионально. "
            f"Формат: {fmt['name']}, размер {img_size}. "
            f"Верни изображение РОВНО {img_size} пикселей. "
            f"Без текста и надписей, если не указано в описании."
        )

    # Списываем генерацию (не при перегенерации)
    if not is_regen:
        if not (user_id == 456504792 and test_mode):
            if get_balance(user_id) <= 0:
                await message.answer(
                    "💎 Генерации закончились.\n\nПополни баланс:",
                    reply_markup=buy_generations_keyboard(),
                )
                return
        if not spend_generation(user_id):
            await message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard(),
            )
            return

    await message.answer("🎨 Генерирую изображение... Обычно это занимает до минуты.")

    logger.info(f"🎨 prompt_image генерация: user={user_id}, mode={mode}, regen={is_regen}")

    try:
        if mode == "photo" and photo:
            img = generate_image(photo, final_prompt)
        else:
            img = generate_image_from_text(final_prompt)
        if not img:
            logger.warning("⚠️ prompt_image: первая попытка не удалась, пробую ещё раз")
            await message.answer("🔄 Сервис задумался, пробую ещё раз...")
            if mode == "photo" and photo:
                img = generate_image(photo, final_prompt)
            else:
                img = generate_image_from_text(final_prompt)
    except Exception as e:
        logger.exception(f"❌ prompt_image: исключение при генерации: {e}")
        img = None

    if not img:
        logger.warning("❌ prompt_image: генерация вернула None")
        # Возвращаем генерацию
        if not is_regen:
            if not (user_id == 456504792 and test_mode):
                from main import free_generations, paid_generations, _save_gen
                free_used = free_generations.get(user_id, 0)
                if free_used > 0:
                    free_generations[user_id] = free_used - 1
                else:
                    paid_generations[user_id] = paid_generations.get(user_id, 0) + 1
                _save_gen()
        state["regen_done"] = False
        prompt_state[user_id] = state
        await message.answer(
            "😔 Не удалось сгенерировать.\n\n"
            "✅ Попытка НЕ списана.\n"
            "🔄 Попробуй ещё раз."
        )
        return

    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    try:
        await message.answer_photo(
            BufferedInputFile(img, filename="prompt_image.jpg"),
            caption=f"🎨 <b>Готово!</b>\n\n💎 Баланс: {balance_text}",
            parse_mode="HTML",
            reply_markup=prompt_result_keyboard(),
        )
    except Exception as e:
        logger.exception(f"❌ prompt_image: ошибка отправки: {e}")
        await message.answer("❌ Не удалось отправить фото.")
