"""
Новогодняя фотосессия с ретро-автомобилем.
Отдельный модуль — не конфликтует с существующими режимами бота.
"""
import json
import os
from datetime import datetime

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)

# ===== СЛОВАРИ =====

XMAS_CARS = {
    "volga_black": {
        "name": "ГАЗ-21 «Волга» — чёрная",
        "short": "🚗 Волга чёрная",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/cars/volga_black.jpg",
        "prompt": "чёрный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, классический советский седан, хромированные детали",
    },
    "volga_red_white": {
        "name": "ГАЗ-21 «Волга» — бело-красная",
        "short": "🚗 Волга бело-красная",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/cars/volga_red_white.jpg",
        "prompt": "двухцветный бело-красный ретро-автомобиль ГАЗ-21 «Волга» 1960-х годов, парадный советский седан, хром",
    },
    "zaz_blue": {
        "name": "Запорожец — голубой",
        "short": "🚗 Запорожец голубой",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/cars/zaz_blue.jpg",
        "prompt": "голубой ретро-автомобиль ЗАЗ-965 «Запорожец» 1960-х годов, компактный советский автомобиль, круглые фары",
    },
}

XMAS_SCENES = {
    "hood": {
        "name": "На капоте",
        "short": "🎅 На капоте",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/hood.jpg",
        "orientation": "portrait",
        "prompt": (
            "Все герои сидят на капоте {car}, позади — большая новогодняя ёлка с гирляндами. "
            "В руках у них — термос, кружки с какао, глинтвейн. Идёт лёгкий снег. "
            "Тёплый вечерний свет, огоньки гирлянд, волшебная атмосфера."
        ),
    },
    "windshield": {
        "name": "Через лобовое стекло",
        "short": "🚗 Через лобовое стекло",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/windshield.jpg",
        "orientation": "landscape",
        "prompt": (
            "Съёмка снаружи через лобовое стекло {car}. Все герои сидят внутри автомобиля, "
            "на панели — маленькая ёлочка и гирлянда. Стекло чуть запотевшее, капли снега. "
            "За окном — зимний вечер, огоньки. Уютная, кинематографичная атмосфера."
        ),
    },
    "arrival": {
        "name": "Прибытие с подарками",
        "short": "🎁 Прибытие с подарками",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/arrival.jpg",
        "orientation": "landscape",
        "prompt": (
            "Все герои выходят из {car} с чемоданами, сумками и коробками с подарками. "
            "Машина стоит, светит фарами в снежную темноту, лучи света видны в морозном воздухе. "
            "Вечер, идёт снег. Сказочное ощущение прибытия в новогоднюю ночь."
        ),
    },
    "tree": {
        "name": "Зимняя сказка на фоне ёлки",
        "short": "🌲 На фоне ёлки",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/tree.jpg",
        "orientation": "portrait",
        "prompt": (
            "{car} стоит чуть в стороне, все герои — на фоне огромной украшенной ёлки с гирляндами. "
            "Сумерки, снег, тёплый свет от гирлянд. Волшебное зимнее настроение."
        ),
    },
    "toast": {
        "name": "С бокалами у машины",
        "short": "🥂 С бокалами",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/toast.jpg",
        "orientation": "portrait",
        "prompt": (
            "Все герои стоят, облокотившись на {car}, в руках бокалы с шампанским или какао. "
            "Смеются, смотрят друг на друга. За машиной — заснеженные ёлки, гирлянды. "
            "Тёплый свет, уютная атмосфера семейного праздника."
        ),
    },
    "window": {
        "name": "Снежный кадр через окно дома",
        "short": "❄️ Через окно дома",
        "preview": "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/scenes/window.jpg",
        "orientation": "landscape",
        "prompt": (
            "Съёмка с улицы через окно дома. За стеклом — все герои внутри дома, "
            "у окна стоит ёлка с гирляндами. На улице, на переднем плане — {car} в снегу. "
            "Двойная композиция: тёплый свет внутри, холодный зимний вечер снаружи. Атмосферно."
        ),
    },
}

XMAS_OUTFITS = {
    "sweaters": {
        "name": "Вязаные свитера",
        "short": "🎄 Свитера с орнаментом",
        "prompt": "в уютных вязаных свитерах с новогодним скандинавским орнаментом (олени, снежинки), красных и зелёных тонов",
    },
    "coats": {
        "name": "Классические пальто",
        "short": "🧥 Пальто",
        "prompt": "в элегантных классических пальто (мужчины — тёмные, женщины — светлые, бежевые), шарфы, перчатки, стиль 60-х",
    },
    "evening": {
        "name": "Вечерние наряды",
        "short": "👗 Вечерние наряды",
        "prompt": "в элегантных вечерних нарядах (платья, костюмы), как на праздничный ужин, изысканно и торжественно",
    },
}

XMAS_TARIFFS = {
    "basic": {
        "name": "Базовый",
        "price": 299,
        "scenes": 1,
        "photos_per_scene": 3,
        "reels": 0,
        "priority": False,
    },
    "optimal": {
        "name": "Оптимальный",
        "price": 699,
        "scenes": 2,
        "photos_per_scene": 3,
        "reels": 1,
        "priority": False,
    },
    "gift": {
        "name": "Подарочный",
        "price": 1290,
        "scenes": 3,
        "photos_per_scene": 4,
        "reels": 2,
        "priority": True,
    },
}

XMAS_SLOTS_FILE = "xmas_slots.json"

# ===== СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЯ =====
# Храним все промежуточные выборы здесь
xmas_state = {}  # {user_id: {"car": ..., "scene": ..., "outfit": ..., "upload_mode": ..., "photos": []}}
xmas_slots = {}  # {user_id: 3} — сколько сценариев осталось


def _load_slots():
    global xmas_slots
    if os.path.exists(XMAS_SLOTS_FILE):
        try:
            with open(XMAS_SLOTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                xmas_slots = {int(k): v for k, v in data.items()}
        except Exception:
            xmas_slots = {}


def _save_slots():
    with open(XMAS_SLOTS_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in xmas_slots.items()}, f, ensure_ascii=False, indent=2)


_load_slots()


def add_xmas_slots(user_id: int, count: int):
    """Начисляет слоты после оплаты. Вызывается из вебхука."""
    xmas_slots[user_id] = xmas_slots.get(user_id, 0) + count
    _save_slots()


def has_xmas_access(user_id: int) -> bool:
    return xmas_slots.get(user_id, 0) > 0


# ===== КЛАВИАТУРЫ =====

def cars_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=car["short"], callback_data=f"xmas_car_{key}")]
        for key, car in XMAS_CARS.items()
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_start")]])


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


def upload_mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍👩‍👧 Все вместе (1 фото)", callback_data="xmas_upload_together")],
        [InlineKeyboardButton(text="👥 По отдельности (до 5 фото)", callback_data="xmas_upload_separate")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_outfit")],
    ])


def tariffs_keyboard():
    rows = []
    for key, t in XMAS_TARIFFS.items():
        rows.append([InlineKeyboardButton(
            text=f"{t['name']} — {t['price']} ₽ ({t['scenes']} сцен.)",
            callback_data=f"xmas_buy_{key}"
        )])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ===== ТЕКСТЫ ЭКРАНОВ =====

XMAS_INTRO = (
    "🎄 <b>Новогодняя фотосессия с ретро-автомобилем</b>\n\n"
    "Пришлите фото своей семьи — я соберу вас вместе в зимней сказке с настоящим ретро-авто. "
    "Ёлки, гирлянды, снег, тёплый свет — как кадр из старого доброго кино.\n\n"
    "📸 <b>Что получите:</b>\n"
    "• 3–12 готовых кадров\n"
    "• Разные ракурсы и планы\n"
    "• С сохранением лиц всех участников\n\n"
    "⏱ Готово за 2–3 минуты\n\n"
    "🎬 <b>Примеры того, что получится — ниже</b>\n\n"
    "Выберите тариф, чтобы начать:"
)

XMAS_NO_ACCESS = (
    "🎄 <b>Новогодняя фотосессия</b>\n\n"
    "Для доступа нужен один из пакетов. Выберите тариф:"
)


# ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====

def register_xmas_handlers(dp):
    """Регистрирует все обработчики новогодней фотосессии."""

    @dp.callback_query(F.data == "xmas_start")
    async def xmas_start(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id

        # Показываем интро с примерами
        # ФОТО-ПРИМЕРЫ: замени ссылки ниже на свои, когда будут готовы
        example_url = "https://raw.githubusercontent.com/photorazev/photo-bot/main/xmas/intro_example.jpg"

        try:
            await callback.message.answer_photo(
                photo=example_url,
                caption=XMAS_INTRO,
                parse_mode="HTML",
                reply_markup=tariffs_keyboard(),
            )
        except Exception:
            # Если фото не найдено — шлём текстом
            await callback.message.answer(
                XMAS_INTRO,
                parse_mode="HTML",
                reply_markup=tariffs_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_back_start")
    async def xmas_back_start(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "🎄 Возвращаемся к началу. Выберите тариф:",
            reply_markup=tariffs_keyboard(),
        )

    # ===== ПОКУПКА =====
    @dp.callback_query(F.data.startswith("xmas_buy_"))
    async def xmas_buy(callback: CallbackQuery):
        await callback.answer()
        tariff_key = callback.data.replace("xmas_buy_", "")
        tariff = XMAS_TARIFFS.get(tariff_key)
        if not tariff:
            await callback.message.answer("❌ Тариф не найден.")
            return

        user_id = callback.from_user.id
        await callback.message.answer(
            f"💳 <b>{tariff['name']} — {tariff['price']} ₽</b>\n\n"
            f"📸 {tariff['scenes']} сцен. × {tariff['photos_per_scene']} кадра\n"
            f"🎬 Reels: {tariff['reels']}\n\n"
            "Оплата будет подключена на следующем этапе. "
            "Пока функция в тестовом режиме — обратитесь к администратору."
        )

    # ===== ВЫБОР МАШИНЫ =====
    @dp.callback_query(F.data == "xmas_choose")
    async def xmas_choose(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id

        if not has_xmas_access(user_id):
            await callback.message.answer(XMAS_NO_ACCESS, parse_mode="HTML", reply_markup=tariffs_keyboard())
            return

        xmas_state[user_id] = {"photos": []}

        await callback.message.answer(
            "🚗 <b>Шаг 1 из 4. Выберите автомобиль:</b>\n\n"
            "Каждая машина — со своим характером.",
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
        xmas_state.setdefault(user_id, {"photos": []})
        xmas_state[user_id]["car"] = car_key

        car = XMAS_CARS[car_key]
        try:
            await callback.message.answer_photo(
                photo=car["preview"],
                caption=f"✅ Выбрано: <b>{car['name']}</b>\n\n🎬 <b>Шаг 2 из 4. Выберите сценарий:</b>",
                parse_mode="HTML",
                reply_markup=scenes_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ Выбрано: <b>{car['name']}</b>\n\n🎬 <b>Шаг 2 из 4. Выберите сценарий:</b>",
                parse_mode="HTML",
                reply_markup=scenes_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_back_car")
    async def xmas_back_car(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "🚗 <b>Выберите автомобиль:</b>",
            reply_markup=cars_keyboard(),
        )

    # ===== ВЫБОР СЦЕНАРИЯ =====
    @dp.callback_query(F.data.startswith("xmas_scene_"))
    async def xmas_scene(callback: CallbackQuery):
        await callback.answer()
        scene_key = callback.data.replace("xmas_scene_", "")
        if scene_key not in XMAS_SCENES:
            await callback.message.answer("❌ Сценарий не найден.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {"photos": []})
        xmas_state[user_id]["scene"] = scene_key

        scene = XMAS_SCENES[scene_key]
        try:
            await callback.message.answer_photo(
                photo=scene["preview"],
                caption=f"✅ Сценарий: <b>{scene['name']}</b>\n\n👗 <b>Шаг 3 из 4. Выберите образ:</b>",
                parse_mode="HTML",
                reply_markup=outfits_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                f"✅ Сценарий: <b>{scene['name']}</b>\n\n👗 <b>Шаг 3 из 4. Выберите образ:</b>",
                parse_mode="HTML",
                reply_markup=outfits_keyboard(),
            )

    @dp.callback_query(F.data == "xmas_back_scene")
    async def xmas_back_scene(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "🎬 <b>Выберите сценарий:</b>",
            reply_markup=scenes_keyboard(),
        )

    # ===== ВЫБОР ОБРАЗА =====
    @dp.callback_query(F.data.startswith("xmas_outfit_"))
    async def xmas_outfit(callback: CallbackQuery):
        await callback.answer()
        outfit_key = callback.data.replace("xmas_outfit_", "")
        if outfit_key not in XMAS_OUTFITS:
            await callback.message.answer("❌ Образ не найден.")
            return

        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {"photos": []})
        xmas_state[user_id]["outfit"] = outfit_key

        outfit = XMAS_OUTFITS[outfit_key]
        await callback.message.answer(
            f"✅ Образ: <b>{outfit['name']}</b>\n\n"
            "📸 <b>Шаг 4 из 4. Как загрузим фото?</b>\n\n"
            "• <b>Все вместе</b> — если у вас есть одно общее фото семьи\n"
            "• <b>По отдельности</b> — если каждый присылает своё фото (до 5 человек)",
            parse_mode="HTML",
            reply_markup=upload_mode_keyboard(),
        )

    @dp.callback_query(F.data == "xmas_back_outfit")
    async def xmas_back_outfit(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "👗 <b>Выберите образ:</b>",
            reply_markup=outfits_keyboard(),
        )

    # ===== РЕЖИМ ЗАГРУЗКИ =====
    @dp.callback_query(F.data == "xmas_upload_together")
    async def xmas_upload_together(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {"photos": []})
        xmas_state[user_id]["upload_mode"] = "together"
        from main import user_mode
        user_mode[user_id] = "xmas_awaiting_photo"

        await callback.message.answer(
            "📸 <b>Пришлите одно общее фото семьи.</b>\n\n"
            "Требования:\n"
            "• Все видны целиком (в полный рост или по грудь)\n"
            "• Лица чёткие, без сильных теней\n"
            "• Хорошее освещение\n\n"
            "После получения фото — сгенерирую серию кадров."
        )

    @dp.callback_query(F.data == "xmas_upload_separate")
    async def xmas_upload_separate(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        xmas_state.setdefault(user_id, {"photos": []})
        xmas_state[user_id]["upload_mode"] = "separate"
        xmas_state[user_id]["photos"] = []
        from main import user_mode
        user_mode[user_id] = "xmas_awaiting_photo"

        await callback.message.answer(
            "📸 <b>Присылайте фото по одному.</b>\n\n"
            "До 5 человек. После каждого фото — кнопки «Добавить ещё» или «Готово».\n\n"
            "Требования к каждому фото:\n"
            "• Человек виден в полный рост или по грудь\n"
            "• Лицо чёткое, свет ровный"
        )


# ===== ОБРАБОТКА ФОТО В РЕЖИМЕ xmas_ =====

async def handle_xmas_photo(message: Message, user_id: int, image_bytes: bytes):
    """
    Ловит фото, когда user_mode начинается на "xmas_".
    Вызывается из main.py в handle_photo.
    """
    state = xmas_state.get(user_id, {})
    mode = state.get("upload_mode", "together")

    if mode == "together":
        state["photos"] = [image_bytes]
        xmas_state[user_id] = state

        await message.answer(
            "✅ Фото получено! Сейчас сгенерирую серию кадров...\n\n"
            "⚠️ Генерация будет подключена на следующем этапе. "
            "Пока это демонстрация конструктора."
        )
        from main import user_mode
        user_mode[user_id] = "free"
        return

    if mode == "separate":
        photos = state.get("photos", [])
        if len(photos) >= 5:
            await message.answer("❌ Максимум 5 человек. Нажмите «Готово».")
            return
        photos.append(image_bytes)
        state["photos"] = photos
        xmas_state[user_id] = state

        count = len(photos)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"➕ Добавить ещё ({count}/5)", callback_data="xmas_more_photo")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="xmas_done_photos")],
        ])
        await message.answer(
            f"✅ Фото {count} получено.\n\n"
            "Пришлите ещё или нажмите «Готово».",
            reply_markup=kb,
        )


# Обработчики для кнопок "добавить ещё" и "готово" — регистрируются в register_xmas_handlers
def register_xmas_photo_handlers(dp):
    @dp.callback_query(F.data == "xmas_more_photo")
    async def xmas_more_photo(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer("📸 Пришлите следующее фото.")

    @dp.callback_query(F.data == "xmas_done_photos")
    async def xmas_done_photos(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        count = len(state.get("photos", []))

        if count == 0:
            await callback.message.answer("❌ Вы не загрузили ни одного фото.")
            return

        await callback.message.answer(
            f"✅ Загружено {count} фото. Сейчас сгенерирую общую сцену...\n\n"
            "⚠️ Генерация будет подключена на следующем этапе."
        )
        from main import user_mode
        user_mode[user_id] = "free"


# Объединяем регистрацию всего
_original_register = register_xmas_handlers
def register_xmas_handlers(dp):  # noqa
    _original_register(dp)
    register_xmas_photo_handlers(dp)
