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
    InputMediaPhoto,
)

logger = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/photorazbor/photo-bot/main"

# ===== ЛОКАЦИИ =====

XMAS_LOCATIONS = {
    "auto": {
        "name": "У ретро-авто",
        "short": "🚗 У ретро-авто",
        "preview": f"{BASE}/xmas/locations/auto.jpg",
        "type": "cars",
        "intro": "Ребята у настоящего ретро-автомобиля, позади — ёлка с гирляндами.",
    },
    "tree": {
        "name": "У ёлки",
        "short": "🌲 У ёлки",
        "preview": f"{BASE}/xmas/locations/tree.jpg",
        "type": "tree_scenes",
        "intro": "Большая украшенная ёлка, гирлянды, зимний вечер.",
    },
    "window": {
        "name": "Через окно дома",
        "short": "🏠 Через окно дома",
        "preview": f"{BASE}/xmas/locations/window.jpg",
        "type": "window_scenes",
        "intro": "Двойная композиция — тёплый свет внутри, холодный вечер снаружи.",
    },
    "fireplace": {
        "name": "У камина",
        "short": "🛋 У камина",
        "preview": f"{BASE}/xmas/locations/fireplace.jpg",
        "type": "fireplace_scenes",
        "intro": "Уютный новогодний интерьер с камином.",
    },
    "forest": {
        "name": "В зимнем лесу",
        "short": "❄️ В зимнем лесу",
        "preview": f"{BASE}/xmas/locations/forest.jpg",
        "type": "forest_scenes",
        "intro": "Заснеженный лес, волшебная новогодняя атмосфера.",
    },
}

# ===== ПОДПУНКТЫ ЛОКАЦИЙ =====

XMAS_CARS = {
    "volga_black": {
        "name": "ГАЗ-21 «Волга» — чёрная",
        "short": "🚗 Волга чёрная",
        "preview": f"{BASE}/xmas/cars/volga_black.jpg",
        "prompt": "чёрный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, классический советский седан, хромированные детали",
    },
    "volga_red_white": {
        "name": "ГАЗ-21 «Волга» — бело-красная",
        "short": "🚗 Волга бело-красная",
        "preview": f"{BASE}/xmas/cars/volga_red_white.jpg",
        "prompt": "двухцветный бело-красный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, парадный советский седан, хром",
    },
    "zaz_blue": {
        "name": "Запорожец — голубой",
        "short": "🚗 Запорожец голубой",
        "preview": f"{BASE}/xmas/cars/zaz_blue.jpg",
        "prompt": "голубой ретро-автомобиль ЗАЗ-965 «Запорожец» 1960-х годов, компактный советский автомобиль, круглые фары",
    },
}

XMAS_TREE_SCENES = {
    "stand": {
        "name": "Стоят у ёлки",
        "short": "🎅 Стоят у ёлки",
        "preview": f"{BASE}/xmas/scenes/tree_stand.jpg",
        "prompt": "стоят рядом с большой украшенной ёлкой с гирляндами, улыбаются, смотрят в камеру",
    },
    "gifts": {
        "name": "Под ёлкой с подарками",
        "short": "🎁 С подарками",
        "preview": f"{BASE}/xmas/scenes/tree_gifts.jpg",
        "prompt": "сидят под большой ёлкой с коробками и подарками в руках, вокруг гирлянды, снег",
    },
    "sit": {
        "name": "Сидят с какао",
        "short": "🕯 Сидят с какао",
        "preview": f"{BASE}/xmas/scenes/tree_sit.jpg",
        "prompt": "сидят на пледе с кружками какао в руках, позади ёлка с гирляндами, тёплый свет",
    },
    "decorate": {
        "name": "Украшают ёлку",
        "short": "✨ Украшают ёлку",
        "preview": f"{BASE}/xmas/scenes/tree_decorate.jpg",
        "prompt": "украшают большую ёлку игрушками и гирляндами, весёлые, вокруг праздничная атмосфера",
    },
}

XMAS_WINDOW_SCENES = {
    "car": {
        "name": "Снаружи машина, внутри вы",
        "short": "🚗 Снаружи машина",
        "preview": f"{BASE}/xmas/scenes/window_car.jpg",
        "prompt": "снято с улицы через окно дома — внутри видны люди, снаружи на переднем плане ретро-автомобиль в снегу",
    },
    "tree": {
        "name": "Внутри ёлка с гирляндами",
        "short": "🎄 Внутри ёлка",
        "preview": f"{BASE}/xmas/scenes/window_tree.jpg",
        "prompt": "снято с улицы через окно дома — внутри люди и большая ёлка с гирляндами, тёплый свет",
    },
    "foggy": {
        "name": "Запотевшее стекло",
        "short": "❄️ Запотевшее стекло",
        "preview": f"{BASE}/xmas/scenes/window_foggy.jpg",
        "prompt": "снято через запотевшее окно, капли и снег на стекле, за стеклом силуэты людей и тёплый свет",
    },
}

XMAS_FIREPLACE_SCENES = {
    "village": {
        "name": "Деревенский дом",
        "short": "🏡 Деревенский дом",
        "preview": f"{BASE}/xmas/scenes/fireplace_village.jpg",
        "prompt": "уютный интерьер деревенского дома — бревенчатые стены, камин, свечи, вязаные пледы, новогодний декор",
    },
    "manor": {
        "name": "Усадьба",
        "short": "🕰 Усадьба",
        "preview": f"{BASE}/xmas/scenes/fireplace_manor.jpg",
        "prompt": "классический интерьер усадьбы — камин, мягкие кресла, свечи, ёлка, винтажный новогодний декор",
    },
    "modern": {
        "name": "Современный интерьер",
        "short": "🛋 Современный",
        "preview": f"{BASE}/xmas/scenes/fireplace_modern.jpg",
        "prompt": "современный уютный интерьер — минимализм, камин, ёлка с гирляндами, тёплый свет",
    },
}

XMAS_FOREST_SCENES = {
    "spruces": {
        "name": "Среди заснеженных елей",
        "short": "🌲 Среди елей",
        "preview": f"{BASE}/xmas/scenes/forest_spruces.jpg",
        "prompt": "среди высоких заснеженных елей в зимнем лесу, идёт снег, волшебная атмосфера",
    },
    "glade": {
        "name": "На поляне с тёплым светом",
        "short": "☀️ На поляне",
        "preview": f"{BASE}/xmas/scenes/forest_glade.jpg",
        "prompt": "на лесной поляне, сквозь ветки пробивается тёплый свет, снег, волшебное зимнее утро",
    },
    "evening": {
        "name": "Вечер с гирляндами",
        "short": "🌙 Вечер с гирляндами",
        "preview": f"{BASE}/xmas/scenes/forest_evening.jpg",
        "prompt": "вечерний зимний лес, между деревьями развешаны гирлянды, тёплый свет, снег",
    },
}

# ===== ОБРАЗЫ =====

XMAS_OUTFITS = {
    "own": {
        "name": "Своя одежда",
        "short": "👕 Своя одежда",
        "preview": f"{BASE}/xmas/outfits/own.jpg",
        "prompt": "оставить одежду с исходного фото без изменений — тот же цвет, фасон, ткань, аксессуары",
    },
    "sweaters": {
        "name": "Новогодние свитера",
        "short": "🎄 Свитера",
        "preview": f"{BASE}/xmas/outfits/sweaters.jpg",
        "prompt": (
            "в ОБЪЁМНЫХ СВОБОДНЫХ вязаных свитерах оверсайз новогодних цветов (красный, зелёный, белый, бежевый), "
            "крупная вязка, свободный крой, свитер слегка объёмный, не обтягивает фигуру. "
            "Брюки — свободные прямые или широкие джинсы, чиносы, брюки-палаццо, НЕ скинни. "
            "Допустимы вязаные шапки и варежки, если они не портят сходство лиц"
        ),
    },
    "coats": {
        "name": "Классические пальто",
        "short": "🧥 Пальто",
        "preview": f"{BASE}/xmas/outfits/coats.jpg",
        "prompt": (
            "в СВОБОДНЫХ ПАЛЬТО ПРЯМОГО СИЛУЭТА оверсайз (бежевые, серые, тёмные), "
            "пальто не в обтяжку, слегка просторное, современный крой, "
            "тёплые объёмные шарфы, перчатки. "
            "Брюки — свободные прямые или широкие, НЕ скинни"
        ),
    },
    "evening": {
        "name": "Вечерние наряды",
        "short": "👗 Вечерние наряды",
        "preview": f"{BASE}/xmas/outfits/evening.jpg",
        "prompt": (
            "в элегантных вечерних нарядах СВОБОДНОГО КРОЯ — платья-миди прямого силуэта, костюмы оверсайз, "
            "тёплые накидки, меховые палантины, изысканно и торжественно, но по погоде. "
            "НЕ обтягивающие, НЕ короткие"
        ),
    },
    "fur": {
        "name": "Шуба",
        "short": "🧥 Шуба",
        "preview": f"{BASE}/xmas/outfits/fur.jpg",
        "prompt": (
            "в элегантной зимней шубе или пуховике свободного кроя, "
            "меховой воротник, объёмная тёплая шапка, роскошно и по-зимнему. "
            "Шуба не в обтяжку, силуэт свободный"
        ),
    },
}

# ===== КОНФИГУРАЦИЯ =====
XMAS_PRICE = 399
XMAS_PAID_FILE = "xmas_paid.json"

# ===== СОСТОЯНИЕ =====
xmas_state = {}
xmas_paid = {}
xmas_awaiting_photo = set()
# временное хранилище для "своего варианта" — чтобы знать, на каком шаге ждём текст
xmas_awaiting_custom = {}  # {user_id: "location" / "subscene" / "outfit"}


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
    xmas_paid[user_id] = True
    _save_paid()


def consume_xmas_payment(user_id: int):
    if user_id in xmas_paid:
        xmas_paid[user_id] = False
        _save_paid()


def has_xmas_payment(user_id: int) -> bool:
    import main
    tm = main.test_mode
    logger.info(f"🔍 has_xmas_payment: user={user_id}, test_mode={tm}, paid={xmas_paid.get(user_id, False)}")
    if user_id == 456504792 and tm:
        return True
    return xmas_paid.get(user_id, False)


# ===== КЛАВИАТУРЫ =====

def locations_keyboard():
    rows = []
    for key, loc in XMAS_LOCATIONS.items():
        rows.append([InlineKeyboardButton(text=loc["short"], callback_data=f"xmas_loc_{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Свой вариант", callback_data="xmas_custom_location")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscene_keyboard(location_type: str):
    mapping = {
        "cars": XMAS_CARS,
        "tree_scenes": XMAS_TREE_SCENES,
        "window_scenes": XMAS_WINDOW_SCENES,
        "fireplace_scenes": XMAS_FIREPLACE_SCENES,
        "forest_scenes": XMAS_FOREST_SCENES,
    }
    items = mapping.get(location_type, {})
    rows = []
    for key, item in items.items():
        rows.append([InlineKeyboardButton(text=item["short"], callback_data=f"xmas_sub_{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Свой вариант", callback_data="xmas_custom_subscene")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_location")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def outfits_keyboard():
    rows = []
    for key, outfit in XMAS_OUTFITS.items():
        rows.append([InlineKeyboardButton(text=outfit["short"], callback_data=f"xmas_outfit_{key}")])
    rows.append([InlineKeyboardButton(text="✏️ Свой вариант", callback_data="xmas_custom_outfit")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_subscene")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="xmas_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_outfit")],
    ])


def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {XMAS_PRICE} ₽", callback_data="xmas_buy")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])


def result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="xmas_regen")],
        [InlineKeyboardButton(text="📷 Загрузить другое фото", callback_data="xmas_upload_again")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

XMAS_INTRO = (
    "🎄 <b>Новогодняя фотосессия</b>\n\n"
    "Пришлите одно общее фото — я соберу вас в зимней сказке: ёлки, гирлянды, снег, тёплый свет.\n\n"
    "📸 <b>Что получите:</b>\n"
    "• 1 готовый кадр\n"
    "• 1 бесплатную перегенерацию\n"
    "• 5 локаций на выбор\n"
    "• 5 образов на выбор\n\n"
    "⏱ Готово за 1–2 минуты\n\n"
    f"💰 Стоимость: <b>{XMAS_PRICE} ₽</b>"
)

XMAS_CHOOSE_LOCATION = "🏙 <b>Шаг 1 из 4. Выберите локацию:</b>"
XMAS_CHOOSE_SUBSCENE = "🎬 <b>Шаг 2 из 4. Выберите композицию:</b>"
XMAS_CHOOSE_OUTFIT = "👗 <b>Шаг 3 из 4. Выберите образ:</b>"
XMAS_UPLOAD = (
    "📸 <b>Шаг 4 из 4. Пришлите фото</b>\n\n"
    "Требования:\n"
    "• Все видны <b>по грудь, по пояс или по колено</b>\n"
    "• Лица крупные, чёткие, без сильных теней\n"
    "• Хорошее освещение, все смотрят в камеру\n\n"
    "⚠️ Чем крупнее лица на исходном фото — тем точнее они сохранятся.\n\n"
    "После получения фото — сгенерирую 1 кадр. Будет 1 бесплатная перегенерация."
)


# ===== ВСПОМОГАТЕЛЬНОЕ =====

async def _send_previews(message, previews: list, caption: str, keyboard):
    """Пробует отправить альбом превью, если не получилось — только текст."""
    photos = [p for p in previews if p]
    if photos:
        try:
            media = [InputMediaPhoto(media=url) for url in photos[:10]]
            await message.answer_media_group(media=media)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить превью: {e}")
    await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)


# ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====

def register_xmas_handlers(dp):
    """Регистрирует все обработчики новогодней фотосессии."""

    # ===== СТАРТ =====
    @dp.callback_query(F.data == "xmas_start")
    async def xmas_start(callback: CallbackQuery):
        await callback.answer()
        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/xmas/intro_example.jpg",
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

    # ===== ОПЛАТА =====
    @dp.callback_query(F.data == "xmas_buy")
    async def xmas_buy(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        logger.info(f"🔍 xmas_buy: user={user_id}, has_payment={has_xmas_payment(user_id)}")

        if has_xmas_payment(user_id):
            await callback.message.answer("✅ Оплата уже получена. Начинаем!")
            await _show_locations(callback.message)
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

    # ===== ШАГ 1: ЛОКАЦИЯ =====
    async def _show_locations(msg):
        previews = [loc["preview"] for loc in XMAS_LOCATIONS.values()]
        await _send_previews(msg, previews, XMAS_CHOOSE_LOCATION, locations_keyboard())

    @dp.callback_query(F.data.startswith("xmas_loc_"))
    async def xmas_location(callback: CallbackQuery):
        await callback.answer()
        loc_key = callback.data.replace("xmas_loc_", "")
        if loc_key not in XMAS_LOCATIONS:
            await callback.message.answer("❌ Локация не найдена.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {})
        xmas_state[user_id] = {"location": loc_key}   # сброс предыдущего выбора

        loc = XMAS_LOCATIONS[loc_key]
        await _show_subscenes(callback.message, loc["type"], loc["name"])

    async def _show_subscenes(msg, location_type, location_name):
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
            "window_scenes": XMAS_WINDOW_SCENES,
            "fireplace_scenes": XMAS_FIREPLACE_SCENES,
            "forest_scenes": XMAS_FOREST_SCENES,
        }
        items = mapping.get(location_type, {})
        previews = [item["preview"] for item in items.values()]
        caption = f"📍 <b>{location_name}</b>\n\n{XMAS_CHOOSE_SUBSCENE}"
        await _send_previews(msg, previews, caption, subscene_keyboard(location_type))

    @dp.callback_query(F.data == "xmas_back_location")
    async def xmas_back_location(callback: CallbackQuery):
        await callback.answer()
        await _show_locations(callback.message)

    @dp.callback_query(F.data == "xmas_custom_location")
    async def xmas_custom_location(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        xmas_awaiting_custom[user_id] = "location"
        await callback.message.answer(
            "✏️ Опишите локацию своими словами.\n\n"
            "Например: «у зимнего озера», «в пряничном домике», «на заснеженной площади»."
        )

    # ===== ШАГ 2: ПОДПУНКТ =====
    @dp.callback_query(F.data.startswith("xmas_sub_"))
    async def xmas_subscene(callback: CallbackQuery):
        await callback.answer()
        sub_key = callback.data.replace("xmas_sub_", "")

        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        loc_key = state.get("location")
        if not loc_key:
            await callback.message.answer("❌ Сначала выберите локацию.")
            return

        loc = XMAS_LOCATIONS[loc_key]
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
            "window_scenes": XMAS_WINDOW_SCENES,
            "fireplace_scenes": XMAS_FIREPLACE_SCENES,
            "forest_scenes": XMAS_FOREST_SCENES,
        }
        items = mapping.get(loc["type"], {})
        if sub_key not in items:
            await callback.message.answer("❌ Композиция не найдена.")
            return

        state["subscene"] = sub_key
        xmas_state[user_id] = state

        await _show_outfits(callback.message)

    @dp.callback_query(F.data == "xmas_back_subscene")
    async def xmas_back_subscene(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        loc_key = state.get("location")
        if not loc_key:
            await _show_locations(callback.message)
            return
        loc = XMAS_LOCATIONS[loc_key]
        await _show_subscenes(callback.message, loc["type"], loc["name"])

    @dp.callback_query(F.data == "xmas_custom_subscene")
    async def xmas_custom_subscene(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        xmas_awaiting_custom[user_id] = "subscene"
        await callback.message.answer(
            "✏️ Опишите композицию своими словами.\n\n"
            "Например: «стоят у багажника», «сидят на санях», «у пряничного домика»."
        )

    # ===== ШАГ 3: ОБРАЗ =====
    async def _show_outfits(msg):
        previews = [o["preview"] for o in XMAS_OUTFITS.values()]
        await _send_previews(msg, previews, XMAS_CHOOSE_OUTFIT, outfits_keyboard())

    @dp.callback_query(F.data.startswith("xmas_outfit_"))
    async def xmas_outfit(callback: CallbackQuery):
        await callback.answer()
        outfit_key = callback.data.replace("xmas_outfit_", "")
        if outfit_key not in XMAS_OUTFITS:
            await callback.message.answer("❌ Образ не найден.")
            return

        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["outfit"] = outfit_key
        xmas_state[user_id] = state

        await _show_upload(callback.message, state)

    @dp.callback_query(F.data == "xmas_back_outfit")
    async def xmas_back_outfit(callback: CallbackQuery):
        await callback.answer()
        await _show_outfits(callback.message)

    @dp.callback_query(F.data == "xmas_custom_outfit")
    async def xmas_custom_outfit(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        xmas_awaiting_custom[user_id] = "outfit"
        await callback.message.answer(
            "✏️ Опишите образ своими словами.\n\n"
            "Например: «в красных шубах с меховыми шапками», «в пижамах с оленями»."
        )

    # ===== ШАГ 4: СВОДКА + ФОТО =====
    async def _show_upload(msg, state):
        loc = XMAS_LOCATIONS.get(state.get("location", ""))
        loc_name = loc["name"] if loc else state.get("custom_location", "—")

        sub_name = "—"
        if state.get("custom_subscene"):
            sub_name = state["custom_subscene"]
        elif loc:
            mapping = {
                "cars": XMAS_CARS,
                "tree_scenes": XMAS_TREE_SCENES,
                "window_scenes": XMAS_WINDOW_SCENES,
                "fireplace_scenes": XMAS_FIREPLACE_SCENES,
                "forest_scenes": XMAS_FOREST_SCENES,
            }
            items = mapping.get(loc["type"], {})
            sub = items.get(state.get("subscene", ""))
            if sub:
                sub_name = sub["name"]

        outfit_name = "—"
        if state.get("custom_outfit"):
            outfit_name = state["custom_outfit"]
        else:
            outfit = XMAS_OUTFITS.get(state.get("outfit", ""))
            if outfit:
                outfit_name = outfit["name"]

        caption = (
            "📋 <b>Ваш выбор:</b>\n\n"
            f"📍 Локация: {loc_name}\n"
            f"🎬 Композиция: {sub_name}\n"
            f"👗 Образ: {outfit_name}\n\n"
            f"{XMAS_UPLOAD}"
        )
        await msg.answer(caption, parse_mode="HTML", reply_markup=upload_keyboard())

    # ===== ЗАГРУЗКА ФОТО =====
    @dp.callback_query(F.data == "xmas_upload")
    async def xmas_upload(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["regen_done"] = False
        xmas_state[user_id] = state
        xmas_awaiting_photo.add(user_id)
        logger.info(f"✅ xmas_upload: user={user_id}, awaiting={xmas_awaiting_photo}")
        await callback.message.answer("📸 Жду фото. Пришлите одно фото.")

    @dp.callback_query(F.data == "xmas_upload_again")
    async def xmas_upload_again(callback: CallbackQuery):
        """Полный сброс и возврат на шаг 1 (локация)."""
        await callback.answer()
        user_id = callback.from_user.id
        xmas_state.pop(user_id, None)
        xmas_awaiting_photo.discard(user_id)
        xmas_awaiting_custom.pop(user_id, None)
        await callback.message.answer(
            "🔄 Начинаем новую фотосессию.\n\n" + XMAS_CHOOSE_LOCATION,
            parse_mode="HTML",
            reply_markup=locations_keyboard()
        )

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


# ===== ОБРАБОТКА ТЕКСТА (свои варианты) =====

async def handle_xmas_custom_text(message: Message, user_id: int, text: str) -> bool:
    """Если пользователь в режиме ввода своего варианта — сохраняет и идёт дальше.
    Возвращает True, если обработал (main.py не должен обрабатывать дальше)."""
    step = xmas_awaiting_custom.get(user_id)
    if not step:
        return False

    text = text.strip()[:300]  # ограничим длину
    if not text:
        await message.answer("✏️ Пусто. Опишите своими словами.")
        return True

    state = xmas_state.get(user_id, {})

    if step == "location":
        state["location"] = None
        state["custom_location"] = text
        xmas_state[user_id] = state
        xmas_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Локация: <b>{text}</b>", parse_mode="HTML")
        # Переходим сразу к образам (свой вариант локации — без подпункта)
        previews = [o["preview"] for o in XMAS_OUTFITS.values()]
        await _send_previews(message, previews, XMAS_CHOOSE_OUTFIT, outfits_keyboard())
        return True

    if step == "subscene":
        state["subscene"] = None
        state["custom_subscene"] = text
        xmas_state[user_id] = state
        xmas_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Композиция: <b>{text}</b>", parse_mode="HTML")
        previews = [o["preview"] for o in XMAS_OUTFITS.values()]
        await _send_previews(message, previews, XMAS_CHOOSE_OUTFIT, outfits_keyboard())
        return True

    if step == "outfit":
        state["outfit"] = None
        state["custom_outfit"] = text
        xmas_state[user_id] = state
        xmas_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Образ: <b>{text}</b>", parse_mode="HTML")
        # Показываем сводку
        await _show_summary_after_custom(message, state)
        return True

    return False


async def _show_summary_after_custom(msg, state):
    loc_name = state.get("custom_location") or (
        XMAS_LOCATIONS.get(state.get("location", ""), {}).get("name", "—")
    )
    sub_name = state.get("custom_subscene") or "—"
    outfit_name = state.get("custom_outfit") or "—"

    caption = (
        "📋 <b>Ваш выбор:</b>\n\n"
        f"📍 Локация: {loc_name}\n"
        f"🎬 Композиция: {sub_name}\n"
        f"👗 Образ: {outfit_name}\n\n"
        f"{XMAS_UPLOAD}"
    )
    await msg.answer(caption, parse_mode="HTML", reply_markup=upload_keyboard())


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

def _build_prompt(state: dict) -> str | None:
    """Собирает финальный промпт из выбора пользователя."""
    # Локация
    loc_key = state.get("location")
    custom_location = state.get("custom_location")
    loc = XMAS_LOCATIONS.get(loc_key) if loc_key else None

    # Подпункт
    sub_text = None
    custom_subscene = state.get("custom_subscene")
    if custom_subscene:
        sub_text = custom_subscene
    elif loc:
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
            "window_scenes": XMAS_WINDOW_SCENES,
            "fireplace_scenes": XMAS_FIREPLACE_SCENES,
            "forest_scenes": XMAS_FOREST_SCENES,
        }
        items = mapping.get(loc["type"], {})
        sub = items.get(state.get("subscene", ""))
        if sub:
            sub_text = sub["prompt"]

    # Образ
    custom_outfit = state.get("custom_outfit")
    outfit = XMAS_OUTFITS.get(state.get("outfit", "")) if not custom_outfit else None
    outfit_text = custom_outfit if custom_outfit else (outfit["prompt"] if outfit else "")

    if not (loc or custom_location):
        return None
    if not sub_text:
        return None
    if not outfit_text:
        return None

    # Если это машина — берём её prompt
    car_text = ""
    if loc and loc["type"] == "cars" and not custom_subscene:
        car = XMAS_CARS.get(state.get("subscene", ""))
        if car:
            car_text = car["prompt"]
            sub_text = f"стоят рядом с {car_text} в разных естественных позах, кто-то облокотился на капот, кто-то рядом, кто-то обнимается"

    # Локация — базовое описание
    if custom_location:
        location_text = custom_location
    else:
        location_text = loc.get("intro", loc["name"])

    # 1 человек или несколько
    face_lock = (
        "КРИТИЧЕСКИ ВАЖНО — СХОДСТВО ЛИЦ: "
        "Лица людей должны быть МАКСИМАЛЬНО ПОХОЖИ на исходное фото — как будто это те же самые люди, сфотографированные в новой обстановке. "
        "Сохрани РОВНО тех людей, что на исходном фото. Если на фото 1 человек — оставь 1, НЕ добавляй никого. Если N человек — оставь ровно N. "
        "СОХРАНИ ТОЧНО: форму лица, овал, разрез и цвет глаз, брови, нос, губы, подбородок, цвет волос, длину волос, возраст, пол, телосложение. "
        "НЕ меняй черты лица, НЕ молоди, НЕ меняй национальность, НЕ стилизуй. "
        "Можно слегка поправить причёску (уложить волосы) и добавить лёгкую естественную ретушь кожи. "
        "ЗАПРЕЩЕНО: подменять лицо, делать «пластиковую куклу», менять форму носа/глаз/губ, менять возраст, добавлять или убирать людей. "
        "Люди должны быть узнаваемы — родственники и друзья должны узнать их на новой фотографии. "
        "Только перенеси их в новую сцену с новым фоном. "
    )

    outfit_lock = (
        f"ОДЕЖДА: {outfit_text}. "
        "СТИЛЬ ОДЕЖДЫ — СОВРЕМЕННЫЙ, СВОБОДНЫЙ, ОВЕРСАЙЗ. "
        "Категорически ЗАПРЕЩЕНО: обтягивающие джинсы-скинни, узкие брюки в облипку, короткие юбки, мини-платья, спортивные штаны, вызывающие наряды, одежда не по размеру, устаревший стиль 2000-х. "
        "НУЖНО: свободные прямые или слегка зауженные брюки, широкие джинсы, брюки-палаццо, чиносы свободного кроя, оверсайз-свитера, свободные пальто прямого силуэта, современный европейский кэжуал. "
        "Одежда должна сидеть свободно, не обтягивать фигуру, не подчёркивать формы. "
        "Стиль как в современных модных журналах — комфортно, элегантно, актуально. "
    )
    
    frame_lock = (
        "КАДР: по грудь, по пояс или по колено. Ноги ниже колена не видны. "
        "Без обуви. Не делай полный рост. "
    )

    location_lock = (
        f"ЛОКАЦИЯ: {location_text}. {sub_text}. "
        "Зимняя атмосфера, снег, тёплый свет, гирлянды. "
    )

    full = (
        f"Новогодняя семейная фотография. "
        f"{face_lock}"
        f"{outfit_lock}"
        f"{frame_lock}"
        f"{location_lock}"
        f"Профессиональная фотография, кинематографичный свет, атмосферно, реалистично. "
        f"Размер: 1024x1024."
    )
    return full


async def _generate_and_send(message: Message, user_id: int, state: dict):
    """Генерирует 1 кадр и отправляет."""
    from ai_service import generate_image

    photo = state.get("photo")
    if not photo:
        await message.answer("❌ Нет фото. Загрузите заново.")
        return

    full_prompt = _build_prompt(state)
    if not full_prompt:
        await message.answer("❌ Не все параметры выбраны. Начните заново: /start")
        return

    if state.get("regen_done"):
        await message.answer("🎨 Генерирую другой вариант...")
    else:
        await message.answer("🎨 Генерирую кадр... Это займёт 1–2 минуты.")

    logger.info(f"🎨 xmas генерация: user={user_id}, regen_done={state.get('regen_done')}")

    try:
        img = generate_image(photo, full_prompt)
    except Exception as e:
        logger.exception(f"❌ xmas: исключение при генерации: {e}")
        img = None

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
