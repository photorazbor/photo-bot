"""
Новогодняя фотосессия с ретро-автомобилем.
Отдельный модуль — не конфликтует с существующими режимами бота.
"""
import os
import json
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

# ===== СЛОВАРИ =====

XMAS_CARS = {
    "volga_black": {
        "name": "ГАЗ-21 «Волга» — чёрная",
        "short": "🚗 Волга чёрная",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/cars/volga_black.jpg",
        "prompt": "чёрный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, классический советский седан, хромированные детали",
    },
    "volga_red_white": {
        "name": "ГАЗ-21 «Волга» — бело-красная",
        "short": "🚗 Волга бело-красная",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/cars/volga_red_white.jpg",
        "prompt": "двухцветный бело-красный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, парадный советский седан, хром",
    },
    "zaz_blue": {
        "name": "Запорожец — голубой",
        "short": "🚗 Запорожец голубой",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/cars/zaz_blue.jpg",
        "prompt": "голубой ретро-автомобиль ЗАЗ-965 «Запорожец» 1960-х годов, компактный советский автомобиль, круглые фары",
    },
}

XMAS_SCENES = {
    "hood": {
        "name": "У машины с ёлкой",
        "short": "🎅 У машины с ёлкой",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/scenes/hood.jpg",
        "orientation": "landscape",
        "prompt": (
            "Все герои стоят рядом с {car} в разных естественных позах — кто-то облокотился на капот, кто-то рядом, кто-то обнимается. "
            "Позади — большая новогодняя ёлка с гирляндами. В руках у них — термос, кружки с какао. Идёт лёгкий снег. "
            "Тёплый вечерний свет, огоньки гирлянд, волшебная атмосфера."
        ),
    },
    "tree": {
        "name": "На фоне большой ёлки",
        "short": "🌲 На фоне ёлки",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/scenes/tree.jpg",
        "orientation": "landscape",
        "prompt": (
            "{car} стоит чуть в стороне, все герои — на фоне огромной украшенной ёлки с гирляндами. "
            "Сумерки, снег, тёплый свет от гирлянд. Волшебное зимнее настроение."
        ),
    },
    "window": {
        "name": "Через окно дома",
        "short": "❄️ Через окно дома",
        "preview": "https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/scenes/window.jpg",
        "orientation": "landscape",
        "prompt": (
            "Съёмка с улицы через окно дома. За стеклом — все герои внутри дома, "
            "у окна стоит ёлка с гирляндами. На улице, на переднем плане — {car} в снегу. "
            "Двойная композиция: тёплый свет внутри, холодный зимний вечер снаружи. Атмосферно."
        ),
    },
}

XMAS_OUTFITS = {
    "own": {
        "name": "Своя одежда",
        "short": "👕 Своя одежда",
        "prompt": "оставить одежду с исходного фото без изменений — тот же цвет, фасон, ткань, аксессуары",
    },
    "sweaters": {
        "name": "Новогодние свитера",
        "short": "🎄 Свитера",
        "prompt": "в тёплых вязаных свитерах новогодних цветов (красный, зелёный, белый), свободный крой",
    },
    "coats": {
        "name": "Классические пальто",
        "short": "🧥 Пальто",
        "prompt": "в классических зимних пальто прямого кроя (тёмные, бежевые, серые), тёплые шарфы, свободный элегантный силуэт",
    },
}

# ===== КОНФИГУРАЦИЯ =====
XMAS_PRICE = 399          # Единая цена за фотосессию
XMAS_PHOTOS = 1           # 1 кадр за фотосессию

XMAS_PAID_FILE = "xmas_paid.json"

# ===== СОСТОЯНИЕ =====
xmas_state = {}                 # {user_id: {"car": ..., "scene": ..., "outfit": ..., "photo": bytes, "regen_done": bool}}
xmas_paid = {}                  # {user_id: True/False} — оплачена ли фотосессия
xmas_awaiting_photo = set()     # user_id, которые ждут фото для новогодней фотосессии


def _load_paid():
    global xmas_paid
    if os.path.exists(XMAS_PAID_FILE):
        try:
            with open(XMAS_PAID_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                xmas_paid = {int(k): v for k, v in data.items()}
        except Exception:
            xmas_paid = {}


def _save_paid():
    with open(XMAS_PAID_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in xmas_paid.items()}, f, ensure_ascii=False, indent=2)


_load_paid()


def grant_xmas_payment(user_id: int):
    """Вызывается из вебхука Точки после оплаты."""
    xmas_paid[user_id] = True
    _save_paid()


def consume_xmas_payment(user_id: int):
    """Списывает оплату после успешной генерации."""
    if user_id in xmas_paid:
        xmas_paid[user_id] = False
        _save_paid()


def has_xmas_payment(user_id: int) -> bool:
    import main
    tm = main.test_mode
    logger.info(f"🔍 has_xmas_payment: user={user_id}, test_mode={tm}, paid={xmas_paid.get(user_id, False)}")
    if user_id == 456504792 and tm:
        logger.info(f"✅ has_xmas_payment: админ в тесте, пропускаем")
        return True
    return xmas_paid.get(user_id, False)


# ===== КЛАВИАТУРЫ =====

def cars_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=car["short"], callback_data=f"xmas_car_{key}")]
        for key, car in XMAS_CARS.items()
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_start")]])


def scenes_keyboard():
    rows = []
    for key, scene in XMAS_SCENES.items():
        rows.append([InlineKeyboardButton(text=scene["short"], callback_data=f"xmas_scene_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_car")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def outfits_keyboard():
    rows = []
    for key, outfit in XMAS_OUTFITS.items():
        rows.append([InlineKeyboardButton(text=outfit["short"], callback_data=f"xmas_outfit_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_scene")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото семьи", callback_data="xmas_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_outfit")],
    ])


def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {XMAS_PRICE} ₽", callback_data="xmas_buy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_start")],
    ])


def result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="xmas_regen")],
        [InlineKeyboardButton(text="📷 Загрузить другое фото", callback_data="xmas_upload_again")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

XMAS_INTRO = (
    "🎄 <b>Новогодняя фотосессия с ретро-автомобилем</b>\n\n"
    "Пришлите <b>одно общее фото семьи</b> — я соберу вас вместе в зимней сказке "
    "с настоящим ретро-авто. Ёлки, гирлянды, снег, тёплый свет — как кадр из старого кино.\n\n"
    "📸 <b>Что получите:</b>\n"
    "• 1 готовый кадр\n"
    "• 1 бесплатную перегенерацию\n"
    "• Сохранение лиц всех участников\n\n"
    "⏱ Готово за 1–2 минуты\n\n"
    f"💰 Стоимость: <b>{XMAS_PRICE} ₽</b>"
)

XMAS_CHOOSE_CAR = "🚗 <b>Шаг 1 из 4. Выберите автомобиль:</b>"
XMAS_CHOOSE_SCENE = "🎬 <b>Шаг 2 из 4. Выберите сценарий:</b>"
XMAS_CHOOSE_OUTFIT = "👗 <b>Шаг 3 из 4. Выберите образ:</b>"
XMAS_UPLOAD = (
    "📸 <b>Шаг 4 из 4. Пришлите фото семьи</b>\n\n"
    "Требования:\n"
    "• Все видны <b>по грудь, по пояс или по колено</b> — так лица получатся чёткими\n"
    "• Лица крупные, без сильных теней\n"
    "• Хорошее освещение, все смотрят в камеру\n\n"
    "⚠️ Чем крупнее лица на исходном фото — тем точнее они сохранятся.\n\n"
    "После получения фото — сгенерирую 1 кадр. Будет 1 бесплатная перегенерация."
)


# ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====

def register_xmas_handlers(dp):
    """Регистрирует все обработчики новогодней фотосессии."""

    @dp.callback_query(F.data == "xmas_start")
    async def xmas_start(callback: CallbackQuery):
        await callback.answer()
        try:
            await callback.message.answer_photo(
                photo="https://raw.githubusercontent.com/photorazbor/photo-bot/main/xmas/intro_example.jpg",
                caption=XMAS_INTRO,
                parse_mode="HTML",
                reply_markup=buy_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                XMAS_INTRO,
                parse_mode="HTML",
                reply_markup=buy_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_buy")
    async def xmas_buy(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        logger.info(f"🔍 xmas_buy: user={user_id}, has_payment={has_xmas_payment(user_id)}")

        if has_xmas_payment(user_id):
            await callback.message.answer("✅ Оплата уже получена. Начинаем!")
            await xmas_choose_car(callback.message)
            return

        from ai_service import create_payment_link
        link = create_payment_link(XMAS_PRICE, "Новогодняя фотосессия с ретро-авто", user_id)
        if not link:
            await callback.message.answer("⚠️ Не удалось создать ссылку. Попробуйте позже.")
            return

        await callback.message.answer(
            f"💳 <b>Оплата новогодней фотосессии — {XMAS_PRICE} ₽</b>\n\n"
            f"В пакет входит 1 кадр + 1 бесплатная перегенерация.\n\n"
            "Если Chrome не открывает страницу — используйте Яндекс Браузер.\n"
            "Это связано с сертификатами Минцифры.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Оплатить {XMAS_PRICE} ₽", url=link)]
            ])
        )

    # ===== ВЫБОР МАШИНЫ =====
    async def xmas_choose_car(msg):
        await msg.answer(
            XMAS_CHOOSE_CAR,
            parse_mode="HTML",
            reply_markup=cars_keyboard(),
        )

    @dp.callback_query(F.data.startswith("xmas_car_"))
    async def xmas_car(callback: CallbackQuery):
        await callback.answer()
        car_key = callback.data.replace("xmas_car_", "")
        if car_key not in XMAS_CARS:
            await callback.message.answer("❌ Машина не найдена.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {})
        xmas_state[user_id]["car"] = car_key

        car = XMAS_CARS[car_key]
        try:
            await callback.message.answer_photo(
                photo=car["preview"],
                caption=f"✅ <b>{car['name']}</b>\n\n{XMAS_CHOOSE_SCENE}",
                parse_mode="HTML",
                reply_markup=scenes_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ <b>{car['name']}</b>\n\n{XMAS_CHOOSE_SCENE}",
                parse_mode="HTML",
                reply_markup=scenes_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_back_car")
    async def xmas_back_car(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(XMAS_CHOOSE_CAR, parse_mode="HTML", reply_markup=cars_keyboard())

    # ===== ВЫБОР СЦЕНАРИЯ =====
    @dp.callback_query(F.data.startswith("xmas_scene_"))
    async def xmas_scene(callback: CallbackQuery):
        await callback.answer()
        scene_key = callback.data.replace("xmas_scene_", "")
        if scene_key not in XMAS_SCENES:
            await callback.message.answer("❌ Сценарий не найден.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {})
        xmas_state[user_id]["scene"] = scene_key

        scene = XMAS_SCENES[scene_key]
        try:
            await callback.message.answer_photo(
                photo=scene["preview"],
                caption=f"✅ <b>{scene['name']}</b>\n\n{XMAS_CHOOSE_OUTFIT}",
                parse_mode="HTML",
                reply_markup=outfits_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ <b>{scene['name']}</b>\n\n{XMAS_CHOOSE_OUTFIT}",
                parse_mode="HTML",
                reply_markup=outfits_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_back_scene")
    async def xmas_back_scene(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(XMAS_CHOOSE_SCENE, parse_mode="HTML", reply_markup=scenes_keyboard())

    # ===== ВЫБОР ОБРАЗА =====
    @dp.callback_query(F.data.startswith("xmas_outfit_"))
    async def xmas_outfit(callback: CallbackQuery):
        await callback.answer()
        outfit_key = callback.data.replace("xmas_outfit_", "")
        if outfit_key not in XMAS_OUTFITS:
            await callback.message.answer("❌ Образ не найден.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {})
        xmas_state[user_id]["outfit"] = outfit_key

        outfit = XMAS_OUTFITS[outfit_key]
        await callback.message.answer(
            f"✅ <b>{outfit['name']}</b>\n\n{XMAS_UPLOAD}",
            parse_mode="HTML",
            reply_markup=upload_keyboard(),
        )

    @dp.callback_query(F.data == "xmas_back_outfit")
    async def xmas_back_outfit(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(XMAS_CHOOSE_OUTFIT, parse_mode="HTML", reply_markup=outfits_keyboard())

    # ===== ЗАГРУЗКА ФОТО =====
    @dp.callback_query(F.data == "xmas_upload")
    async def xmas_upload(callback: CallbackQuery):
        logger.info(f"🚀 xmas_upload: user={callback.from_user.id}")
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["regen_done"] = False
        xmas_state[user_id] = state
        xmas_awaiting_photo.add(user_id)
        logger.info(f"✅ xmas_upload: awaiting={xmas_awaiting_photo}")
        await callback.message.answer("📸 Жду фото семьи. Пришлите одно фото.")

    @dp.callback_query(F.data == "xmas_upload_again")
    async def xmas_upload_again(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["regen_done"] = False
        xmas_state[user_id] = state
        xmas_awaiting_photo.add(user_id)
        await callback.message.answer("📸 Жду новое фото семьи.")

    # ===== ПЕРЕГЕНЕРАЦИЯ =====
    @dp.callback_query(F.data == "xmas_regen")
    async def xmas_regen(callback: CallbackQuery):
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        if not state.get("photo"):
            await callback.answer("❌ Нет фото. Загрузите заново.", show_alert=True)
            return
        if state.get("regen_done"):
            await callback.answer(
                "Перегенерация уже использована. Загрузите новое фото.",
                show_alert=True,
            )
            return
        state["regen_done"] = True
        xmas_state[user_id] = state
        await callback.answer("🎨 Генерирую другой вариант...")
        await _generate_and_send(callback.message, user_id, state)


# ===== ОБРАБОТКА ФОТО =====

async def handle_xmas_photo(message: Message, user_id: int, image_bytes: bytes):
    """Вызывается из main.py, когда пользователь в режиме xmas_awaiting_photo."""
    state = xmas_state.get(user_id, {})
    state["photo"] = image_bytes
    state["regen_done"] = False
    xmas_state[user_id] = state

    xmas_awaiting_photo.discard(user_id)

    await message.answer("✅ Фото получено! Генерирую кадр. Это займёт 1–2 минуты...")
    await _generate_and_send(message, user_id, state)


# ===== ГЕНЕРАЦИЯ =====

async def _generate_and_send(message: Message, user_id: int, state: dict):
    """Генерирует 1 кадр и отправляет."""
    from ai_service import generate_image

    car = XMAS_CARS.get(state.get("car"))
    scene = XMAS_SCENES.get(state.get("scene"))
    outfit = XMAS_OUTFITS.get(state.get("outfit"))
    photo = state.get("photo")

    if not all([car, scene, outfit, photo]):
        await message.answer("❌ Не все параметры выбраны. Начните заново: /start")
        return

    base_prompt = scene["prompt"].format(car=car["prompt"])
    outfit_text = outfit["prompt"]

    face_lock = (
        "КРИТИЧЕСКИ ВАЖНО: это ФОТОРЕАЛИСТИЧНАЯ замена лиц. "
        "Сохрани АБСОЛЮТНО ТОЧНО лица, черты, причёски, цвет волос, цвет глаз, возраст, пол и телосложение КАЖДОГО человека с исходного фото. "
        "Лица не должны быть изменены, улучшены, стилизованы или приукрашены. "
        "НЕ меняй людей, НЕ добавляй и НЕ убирай людей. "
        "Только перенеси их в новую сцену с новым фоном. "
    )

    outfit_lock = (
        f"ОДЕЖДА: {outfit_text}. "
        "НЕ меняй одежду на обтягивающие джинсы, короткие юбки, мини-платья, спортивные штаны или вызывающие наряды. "
        "Силуэт свободный и естественный. "
    )

    frame_lock = (
        "КАДР: по грудь, по пояс или по колено. Ноги ниже колена не видны. "
        "Без обуви и без полного роста. "
    )

    location_lock = (
        f"ЛОКАЦИЯ: зимняя улица, вечер, идёт снег. {base_prompt} "
        f"Машина: {car['prompt']}. "
    )

    full_prompt = (
        f"Новогодняя семейная фотография. "
        f"{face_lock}"
        f"{outfit_lock}"
        f"{frame_lock}"
        f"{location_lock}"
        f"Профессиональная фотография, кинематографичный свет, атмосферно, реалистично. "
        f"Размер: 1024x1024."
    )

    if state.get("regen_done"):
        await message.answer("🎨 Генерирую другой вариант...")
    else:
        await message.answer("🎨 Генерирую кадр... Это займёт 1–2 минуты.")

    logger.info(f"🎨 xmas генерация: user={user_id}, regen_done={state.get('regen_done')}")

    img = generate_image(photo, full_prompt)
    if not img:
        logger.warning(f"❌ xmas: generate_image вернул None")
        await message.answer(
            "😔 Не удалось сгенерировать кадр.\n\n"
            "✅ Попытка НЕ списана.\n"
            "🔄 Нажми «Перегенерировать» ещё раз."
        )
        return

    logger.info(f"✅ xmas: кадр получен")

    try:
        await message.answer_photo(
            BufferedInputFile(img, filename="xmas.jpg"),
            caption="🎄 <b>Готово!</b>",
            parse_mode="HTML",
            reply_markup=result_keyboard(),
        )
    except Exception as e:
        logger.exception(f"❌ xmas: ошибка отправки фото: {e}")
        await message.answer("❌ Не удалось отправить фото.")

    if not state.get("regen_done"):
        consume_xmas_payment(user_id)
