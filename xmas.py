"""
Новогодняя фотосессия с ретро-автомобилем.
Работает через общий баланс генераций из main.py.
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

# ===== ФОРМАТЫ =====

XMAS_FORMATS = {
    "original": {"name": "📐 Исходный", "short": "📐 Исходный", "desc": "как на исходном фото"},
    "1_1": {"name": "📱 1:1 (квадрат)", "short": "📱 1:1 (квадрат)", "desc": "квадратная композиция"},
    "3_4": {"name": "📱 3:4 (вертикаль)", "short": "📱 3:4 (вертикаль)", "desc": "вертикальная композиция"},
    "4_3": {"name": "🖼 4:3 (горизонт)", "short": "🖼 4:3 (горизонт)", "desc": "горизонтальная композиция"},
    "4_5": {"name": "📱 4:5 (Instagram)", "short": "📱 4:5 (Instagram)", "desc": "вертикаль для Instagram"},
    "9_16": {"name": "📱 9:16 (сторис)", "short": "📱 9:16 (сторис)", "desc": "полная вертикаль для сторис"},
}

# ===== СТИЛИЗАЦИИ =====

XMAS_STYLES = {
    "realistic": {
        "name": "🎬 Реалистичное фото",
        "short": "🎬 Реалистичное",
        "prompt": "",
    },
    "soviet_card": {
        "name": "🎄 Советская открытка",
        "short": "🎄 Советская открытка",
        "prompt": (
            "СТИЛИЗАЦИЯ: советская новогодняя открытка 1960–70-х годов. "
            "ЭТО РИСОВАННАЯ ИЛЛЮСТРАЦИЯ, А НЕ ФОТОГРАФИЯ. "
            "Плоские рисованные формы, живописный стиль, тёплые приглушённые тона — красно-зелёно-золотые, "
            "декоративные снежинки, лёгкая текстура старой бумаги, чёрные контуры. "
            "Люди нарисованы, как в советских открытках — плоские, стилизованные. "
        ),
    },
    "soviet_fairy": {
        "name": "🐰 Советская сказка",
        "short": "🐰 Советская сказка",
        "prompt": (
            "СТИЛИЗАЦИЯ: советская новогодняя открытка 1960–70-х годов. "
            "ЖИВОПИСНАЯ ИЛЛЮСТРАЦИЯ, нарисованная от руки кистью или акварелью. "
            "НЕ фотография, НЕ цифровой вектор. "
            "\n\n"
            "ЖИВОПИСНОСТЬ: "
            "видны мазки кисти, мягкие акварельные заливки, "
            "плавные переходы цвета. "
            "Линии мягкие, чуть неровные — как от руки. "
            "Не идеально ровные, не цифровые. "
            "Стиль как у советских детских книг 60-х и открыток того времени. "
            "\n\n"
            "ЗЕРНИСТОСТЬ: "
            "лёгкая плёночная зернистость по всей картинке — "
            "как будто изображение напечатано в типографии на плёнке, "
            "а не создано в цифре. "
            "Мягкая шероховатость, но БЕЗ текстуры старой бумаги, "
            "БЕЗ потёртостей, БЕЗ заломов, БЕЗ пятен от времени. "
            "\n\n"
            "ЦВЕТА: "
            "приглушённые, но НЕ выцветшие в жёлтый. "
            "Красные — тёплые, чуть приглушённые. "
            "Зелёные — оливково-изумрудные. "
            "Голубые — серо-голубые, мягкие. "
            "Золотые — охра и тёплое золото. "
            "Общая палитра тёплая, винтажная, но живая. "
            "\n\n"
            "ВИНЬЕТКА: "
            "лёгкое затемнение по краям кадра — как у старых открыток. "
            "НЕ потёртости, НЕ заломы, а мягкое затемнение. "
            "\n\n"
            "ЛЮДИ: нарисованные персонажи в живописной стилизации. "
            "Лица узнаваемые с исходного фото, но нарисованные мягко. "
            "Одежда — по выбранному образу, в советском стиле: "
            "шубы, тулупы, валенки, шапки-ушанки, вязаные свитера, "
            "пуховые платки, варежки, меховые воротники. "
            "\n\n"
            "ЗВЕРИ-ПЕРСОНАЖИ: вокруг людей — советские сказочные звери: "
            "зайцы, белки, медвежата, снегири, снеговики. "
            "Нарисованы в том же живописном стиле, добрые, с улыбками, "
            "могут держать подарки, музыкальные инструменты, "
            "ёлочные игрушки, мандарины, лыжи, санки. "
            "\n\n"
            "ДЕКОРАТИВНЫЕ ЭЛЕМЕНТЫ: снежинки, звёзды, месяц, "
            "ёлочные игрушки (шары, шишки, ракеты, сосульки), "
            "ёлки в снегу, гирлянды, сугробы. "
            "\n\n"
            "ТЕКСТ НА ОТКРЫТКЕ: крупный рукописный текст «С Новым годом!» "
            "нарисованный от руки, курсивом. "
            "Красный или тёмно-синий. Без других надписей. "
            "\n\n"
            "КОМПОЗИЦИЯ: люди в центре, звери вокруг, ёлка, зимний лес или поляна. "
            "\n\n"
            "ГЛАВНОЕ: результат — ЖИВОПИСНАЯ РУЧНАЯ РАБОТА в советском стиле, "
            "с мазками и мягкими линиями, "
            "с лёгкой зернистостью как у типографской печати. "
            "НЕ цифровая иллюстрация, НЕ фотореализм, НЕ состаренная бумага."
        ),
    },
    "soviet_cartoon": {
        "name": "📺 Советский мультик",
        "short": "📺 Советский мультик",
        "prompt": (
            "СТИЛИЗАЦИЯ: советская рисованная анимация 1960–70-х годов, "
            "как в мультфильмах «Ёжик в тумане», «Двенадцать месяцев», «Снежная королева». "
            "ЭТО РИСОВАННЫЙ МУЛЬТФИЛЬМ, А НЕ ФОТОГРАФИЯ. "
            "Акварельные фоны, рисованные плоские персонажи, мягкие пастельные тона, "
            "контурная обводка, тёплый свет, наивный добрый стиль. "
        ),
    },
    "disney": {
        "name": "🐭 Диснеевский мультик",
        "short": "🐭 Диснеевский",
        "prompt": (
            "ВАЖНО: ЭТО 3D-МУЛЬТФИЛЬМ, А НЕ ФОТОГРАФИЯ. "
            "Стиль современной диснеевской 3D-анимации (Pixar/Disney). "
            "Мультяшные 3D-персонажи с БОЛЬШИМИ выразительными глазами, "
            "мягкие округлые формы лиц, гладкие рендер-поверхности, "
            "яркие тёплые цвета, пушистые волосы. "
            "Стиль как в мультфильмах «Холодное сердце», «Моана», «Рапунцель». "
            "Люди нарисованы в 3D, но УЗНАВАЕМЫ — те же черты лица, "
            "упрощённые и стилизованные. "
            "СОХРАНИ всех людей с фото — никого не убирай и не добавляй. "
            "Фон — стилизованный, как в мультфильме. "
            "ГЛАВНОЕ: результат должен выглядеть КАК КАДР ИЗ МУЛЬТФИЛЬМА, "
            "а НЕ как фотография с фильтром. "
            "НЕ реализм. НЕ фото. ТОЛЬКО 3D-мультфильм."
        ),
    },
    "comics": {
        "name": "💥 Комикс с раскадровкой",
        "short": "💥 Комикс",
        "prompt": (
            "СТИЛИЗАЦИЯ: новогодний комикс с раскадровкой из 3 панелей на одной картинке. "
            "ЭТО КОМИКС, А НЕ ФОТОГРАФИЯ. "
            "Три кадра одной истории: на всех — те же люди, разные ракурсы или моменты. "
            "ЯРКИЙ РИСОВАННЫЙ КОМИКС-СТИЛЬ: чёрные жирные контуры, плоские яркие цвета, "
            "штриховка (halftone dots), динамичные позы. "
            "В каждой панели — короткая надпись на РУССКОМ языке, читаемая, по смыслу подходит к сцене. "
            "ЖЁСТКОЕ ПРАВИЛО ПО ЛЮДЯМ: "
            "посчитай ТОЧНОЕ количество людей на исходном фото. "
            "На КАЖДОЙ из 3 панелей должно быть РОВНО столько же людей. "
            "НЕ добавляй ни одного нового персонажа. "
            "НЕ убирай ни одного человека с исходного фото. "
            "ЗАПРЕЩЕНО придумывать новых персонажей. "
            "ЗАПРЕЩЕНО терять людей с исходного фото. "
            "ЖЁСТКОЕ ПРАВИЛО ПО ОДЕЖДЕ И ВНЕШНОСТИ: "
            "на ВСЕХ 3 панелях у каждого персонажа должна быть ОДНА И ТА ЖЕ ОДЕЖДА — "
            "тот же цвет, фасон, детали. "
            "Эта одежда уже задана в промпте выше (см. блок ОДЕЖДА) — "
            "используй ИМЕННО её на всех 3 панелях без изменений. "
            "НЕ меняй одежду между панелями. "
            "НЕ меняй причёску, цвет волос, аксессуары между панелями. "
            "Если на первой панели персонаж в красном свитере — "
            "на второй и третьей он ТОЖЕ в красном свитере. "
            "Все персонажи должны выглядеть ОДИНАКОВО на всех панелях — "
            "меняется только поза и ракурс, но НЕ внешность и НЕ одежда. "
        ),
    },
}

# ===== СОСТОЯНИЕ =====
xmas_state = {}                 # {user_id: {...}}
xmas_awaiting_photo = set()     # user_id, ждущие фото
xmas_awaiting_custom = {}       # {user_id: "location" / "subscene" / "outfit"}


def is_user_in_xmas_flow(user_id: int) -> bool:
    """True, если пользователь в середине флоу xmas, но НЕ на шаге загрузки фото."""
    return user_id in xmas_state and user_id not in xmas_awaiting_photo

def reset_xmas_state(user_id: int):
    """Сбрасывает состояние xmas для пользователя (при выходе в другое меню)."""
    xmas_state.pop(user_id, None)
    xmas_awaiting_photo.discard(user_id)
    xmas_awaiting_custom.pop(user_id, None)


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


def formats_keyboard():
    rows = []
    for key, fmt in XMAS_FORMATS.items():
        rows.append([InlineKeyboardButton(text=fmt["short"], callback_data=f"xmas_fmt_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_outfit")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def styles_keyboard():
    rows = []
    for key, style in XMAS_STYLES.items():
        rows.append([InlineKeyboardButton(text=style["short"], callback_data=f"xmas_style_{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_format")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def upload_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="xmas_upload")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_style")],
    ])


def result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перегенерировать — бесплатно", callback_data="xmas_regen")],
        [InlineKeyboardButton(text="📷 Загрузить другое фото", callback_data="xmas_upload_again")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])


# ===== ТЕКСТЫ =====

XMAS_INTRO = (
    "🎄 <b>Новогодняя фотосессия</b>\n\n"
    "Пришли одно общее фото — я соберу вас в зимней сказке: ёлки, гирлянды, снег, тёплый свет.\n\n"
    "📸 <b>Что получишь:</b>\n"
    "• 1 готовый кадр\n"
    "• 1 бесплатную перегенерацию\n"
    "• 4 локации на выбор\n"
    "• 5 образов на выбор\n"
    "• 6 форматов на выбор\n"
    "• 6 стилизаций на выбор\n\n"
    "💎 <b>Стоимость:</b> 1 генерация с твоего баланса\n\n"
    "⚠️ Результат — художественная стилизация. 100% сходства не гарантируется, "
    "но если что-то не понравится — 1 перегенерация бесплатна."
)

XMAS_CHOOSE_STYLE = "🎨 <b>Шаг 1 из 6. Выбери стиль:</b>"
XMAS_CHOOSE_LOCATION = "🏙 <b>Шаг 2 из 6. Выбери локацию:</b>"
XMAS_CHOOSE_SUBSCENE = "🎬 <b>Шаг 3 из 6. Выбери композицию:</b>"
XMAS_CHOOSE_OUTFIT = "👗 <b>Шаг 4 из 6. Выбери образ:</b>"
XMAS_CHOOSE_FORMAT = "📐 <b>Шаг 5 из 6. Выбери формат кадра:</b>"
XMAS_UPLOAD = (
    "📸 <b>Шаг 6 из 6. Пришли фото</b>\n\n"
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

        from main import get_balance, test_mode, buy_generations_keyboard
        user_id = callback.from_user.id
        balance = get_balance(user_id)

        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс — и начнём:",
                reply_markup=buy_generations_keyboard()
            )
            return

        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/xmas/intro_example.jpg",
                caption=XMAS_INTRO + "\n\n" + XMAS_CHOOSE_STYLE,
                parse_mode="HTML",
                reply_markup=styles_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                XMAS_INTRO + "\n\n" + XMAS_CHOOSE_STYLE,
                parse_mode="HTML",
                reply_markup=styles_keyboard(),
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
        xmas_state[user_id] = {"location": loc_key}

        loc = XMAS_LOCATIONS[loc_key]
        await _show_subscenes(callback.message, loc["type"], loc["name"])

    async def _show_subscenes(msg, location_type, location_name):
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
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
            "✏️ Опиши локацию своими словами.\n\n"
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
            await callback.message.answer("❌ Сначала выбери локацию.")
            return

        loc = XMAS_LOCATIONS[loc_key]
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
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
            "✏️ Опиши композицию своими словами.\n\n"
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

        await _show_formats(callback.message)

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
            "✏️ Опиши образ своими словами.\n\n"
            "Например: «в красных шубах с меховыми шапками», «в пижамах с оленями»."
        )

    # ===== ШАГ 4: ФОРМАТ =====
    async def _show_formats(msg):
        await msg.answer(XMAS_CHOOSE_FORMAT, parse_mode="HTML", reply_markup=formats_keyboard())

    @dp.callback_query(F.data.startswith("xmas_fmt_"))
    async def xmas_format(callback: CallbackQuery):
        await callback.answer()
        fmt_key = callback.data.replace("xmas_fmt_", "")
        if fmt_key not in XMAS_FORMATS:
            await callback.message.answer("❌ Формат не найден.")
            return

        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["format"] = fmt_key
        xmas_state[user_id] = state

        await _show_upload(callback.message, state)

    @dp.callback_query(F.data == "xmas_back_format")
    async def xmas_back_format(callback: CallbackQuery):
        await callback.answer()
        await _show_formats(callback.message)

    # ===== ШАГ 5: СТИЛЬ =====
    async def _show_styles(msg):
        await msg.answer(XMAS_CHOOSE_STYLE, parse_mode="HTML", reply_markup=styles_keyboard())

    @dp.callback_query(F.data.startswith("xmas_style_"))
    async def xmas_style(callback: CallbackQuery):
        await callback.answer()
        style_key = callback.data.replace("xmas_style_", "")
        if style_key not in XMAS_STYLES:
            await callback.message.answer("❌ Стиль не найден.")
            return

        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["style"] = style_key
        xmas_state[user_id] = state

        style_name = XMAS_STYLES[style_key]["name"]

        # Показываем пример для стиля (если есть картинки)
        await callback.message.answer(
            f"🎨 <b>Стиль: {style_name}</b>\n\n"
            "Вот пример — как преображается фото:",
            parse_mode="HTML"
        )
        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/examples/xmas/{style_key}/before.jpg",
                caption="📷 <b>ДО</b> — обычное фото",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"⚠️ Нет before.jpg для {style_key}: {e}")
        try:
            await callback.message.answer_photo(
                photo=f"{BASE}/examples/xmas/{style_key}/after.jpg",
                caption=f"✨ <b>ПОСЛЕ</b> — {style_name}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"⚠️ Нет after.jpg для {style_key}: {e}")
            
        # Особый случай — советская сказка (выбор композиции)
        if style_key == "soviet_fairy":
            await callback.message.answer(
                "🎄 <b>Как расположить персонажей?</b>\n\n"
                "🐰 В этом стиле появятся Дед Мороз, Снегурочка "
                "и советские сказочные звери.\n\n"
                "Выбери композицию:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎄 Обычная композиция", callback_data="xmas_arrange_normal")],
                    [InlineKeyboardButton(text="💫 Хоровод", callback_data="xmas_arrange_chorovod")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="xmas_back_style")],
                ])
            )
            return

        # Дальше — выбор локации
        await callback.message.answer(
            XMAS_CHOOSE_LOCATION,
            parse_mode="HTML",
            reply_markup=locations_keyboard()
        )

    @dp.callback_query(F.data == "xmas_arrange_normal")
    async def xmas_arrange_normal(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["chorovod"] = False
        xmas_state[user_id] = state
        await callback.message.answer(
            XMAS_CHOOSE_LOCATION,
            parse_mode="HTML",
            reply_markup=locations_keyboard()
        )

    @dp.callback_query(F.data == "xmas_arrange_chorovod")
    async def xmas_arrange_chorovod(callback: CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        state = xmas_state.get(user_id, {})
        state["chorovod"] = True
        xmas_state[user_id] = state
        await callback.message.answer(
            XMAS_CHOOSE_LOCATION,
            parse_mode="HTML",
            reply_markup=locations_keyboard()
        )

    @dp.callback_query(F.data == "xmas_back_style")
    async def xmas_back_style(callback: CallbackQuery):
        await callback.answer()
        await _show_styles(callback.message)

    # ===== ШАГ 6: СВОДКА + ФОТО =====
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

        fmt_name = "—"
        fmt = XMAS_FORMATS.get(state.get("format", ""))
        if fmt:
            fmt_name = fmt["name"]

        style_name = "—"
        style = XMAS_STYLES.get(state.get("style", ""))
        if style:
            style_name = style["name"]

        caption = (
            "📋 <b>Твой выбор:</b>\n\n"
            f"📍 Локация: {loc_name}\n"
            f"🎬 Композиция: {sub_name}\n"
            f"👗 Образ: {outfit_name}\n"
            f"📐 Формат: {fmt_name}\n"
            f"🎨 Стиль: {style_name}\n\n"
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
        await callback.message.answer("📸 Жду фото. Пришли одно фото.")

    @dp.callback_query(F.data == "xmas_upload_again")
    async def xmas_upload_again(callback: CallbackQuery):
        """Полный сброс и возврат на шаг 1 (локация)."""
        await callback.answer()
        user_id = callback.from_user.id
        xmas_state.pop(user_id, None)
        xmas_awaiting_photo.discard(user_id)
        xmas_awaiting_custom.pop(user_id, None)

        from main import get_balance, test_mode, buy_generations_keyboard
        balance = get_balance(user_id)
        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс — и начнём:",
                reply_markup=buy_generations_keyboard()
            )
            return

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
            await callback.answer("❌ Нет фото. Загрузи заново.", show_alert=True)
            return
        if state.get("regen_done"):
            await callback.answer(
                "Перегенерация уже использована. Загрузи новое фото.",
                show_alert=True,
            )
            return
        state["regen_done"] = True
        xmas_state[user_id] = state
        await callback.answer("🎨 Генерирую другой вариант...")
        await _generate_and_send(callback.message, user_id, state)


# ===== ОБРАБОТКА ТЕКСТА (свои варианты) =====

async def handle_xmas_custom_text(message: Message, user_id: int, text: str) -> bool:
    """Если пользователь в режиме ввода своего варианта — сохраняет и идёт дальше."""
    step = xmas_awaiting_custom.get(user_id)
    if not step:
        return False

    text = text.strip()[:300]
    if not text:
        await message.answer("✏️ Пусто. Опиши своими словами.")
        return True

    state = xmas_state.get(user_id, {})

    if step == "location":
        state["location"] = None
        state["custom_location"] = text
        xmas_state[user_id] = state
        xmas_awaiting_custom.pop(user_id, None)
        await message.answer(f"✅ Локация: <b>{text}</b>", parse_mode="HTML")
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
        await message.answer(XMAS_CHOOSE_FORMAT, parse_mode="HTML", reply_markup=formats_keyboard())
        return True

    return False


# ===== ОБРАБОТКА ФОТО =====

async def handle_xmas_photo(message: Message, user_id: int, image_bytes: bytes):
    """Вызывается из main.py, когда пользователь в режиме xmas_awaiting_photo."""
    state = xmas_state.get(user_id, {})
    state["photo"] = image_bytes
    state["regen_done"] = False
    xmas_state[user_id] = state

    xmas_awaiting_photo.discard(user_id)

    await message.answer("✅ Фото получено!")
    await _generate_and_send(message, user_id, state)


# ===== ГЕНЕРАЦИЯ =====

def _build_prompt(state: dict) -> str | None:
    """Собирает финальный промпт из выбора пользователя."""
    loc_key = state.get("location")
    custom_location = state.get("custom_location")
    loc = XMAS_LOCATIONS.get(loc_key) if loc_key else None

    sub_text = None
    custom_subscene = state.get("custom_subscene")
    if custom_subscene:
        sub_text = custom_subscene
    elif loc:
        mapping = {
            "cars": XMAS_CARS,
            "tree_scenes": XMAS_TREE_SCENES,
            "fireplace_scenes": XMAS_FIREPLACE_SCENES,
            "forest_scenes": XMAS_FOREST_SCENES,
        }
        items = mapping.get(loc["type"], {})
        sub = items.get(state.get("subscene", ""))
        if sub:
            sub_text = sub["prompt"]

    custom_outfit = state.get("custom_outfit")
    outfit = XMAS_OUTFITS.get(state.get("outfit", "")) if not custom_outfit else None
    outfit_text = custom_outfit if custom_outfit else (outfit["prompt"] if outfit else "")

    if not (loc or custom_location):
        return None
    if not sub_text:
        return None
    if not outfit_text:
        return None

    if loc and loc["type"] == "cars" and not custom_subscene:
        car = XMAS_CARS.get(state.get("subscene", ""))
        if car:
            car_text = car["prompt"]
            sub_text = f"стоят рядом с {car_text} в разных естественных позах, кто-то облокотился на капот, кто-то рядом, кто-то обнимается"

    if custom_location:
        location_text = custom_location
    else:
        location_text = loc.get("intro", loc["name"])

    # Блок про хоровод — только для советской сказки
    chorovod_lock = ""
    if state.get("style") == "soviet_fairy" and state.get("chorovod"):
        chorovod_lock = (
            "КОМПОЗИЦИЯ — ХОРОВОД: "
            "Все персонажи встали в круг и водят хоровод. "
            "Держатся за руки, улыбаются, движение по кругу. "
            "\n\n"
            "МЕСТО: локацию бери из блока ЛОКАЦИЯ ниже. "
            "Если выбрана усадьба или деревенский дом — "
            "хоровод ВНУТРИ помещения: камин, свечи, кресла, ковры, ёлка в углу. "
            "Если выбран зимний лес — хоровод на улице среди ёлок. "
            "Если выбрана ёлка или ретро-авто — на улице. "
            "НЕ ставь хоровод на улицу, если локация — интерьер. "
            "\n\n"
            "КТО В КРУГУ — ЖЁСТКО: "
            "1) люди с исходного фото (ровно сколько на фото), "
            "2) Дед Мороз, "
            "3) Снегурочка, "
            "4) звери — зайцы, белки, медвежата, снегири, снеговики. "
            "НЕ добавляй других людей — ни детей, ни взрослых, ни прохожих. "
            "Если круг неполный — добавь БОЛЬШЕ ЗВЕРЕЙ, а не людей. "
            "Дед Мороз — красная шуба, посох, борода. "
            "Снегурочка — голубая шуба, кокошник. "
            "Все радостные, праздничные. "
        )

    face_lock = (
        "КОЛИЧЕСТВО ЛЮДЕЙ: посчитай ТОЧНО, сколько людей на исходном фото. "
        "На новой картинке — РОВНО СТОЛЬКО ЖЕ. "
        "Один = один. Двое = двое. Шесть = шесть. "
        "НЕ добавляй никого. НЕ убирай никого. НЕ заменяй. "
        "Все люди с исходного фото — на новой картинке. "
        "ЗАПРЕЩЕНО: прохожие, силуэты, фигуры вдалеке. "
        "ЗАПРЕЩЕНО: терять людей, менять одного на другого. "
    )

    outfit_lock = (
        f"ОДЕЖДА: {outfit_text}. "
        "Стиль современный, свободный, оверсайз. "
        "ЗАПРЕЩЕНО: скинни, обтягивающие брюки, короткие юбки, мини-платья, "
        "спортивные штаны, вызывающие наряды, устаревший стиль 2000-х. "
        "НУЖНО: свободные прямые или широкие брюки, джинсы, чиносы, "
        "оверсайз-свитера, свободные пальто. "
        "Одежда сидит свободно, не обтягивает фигуру. "
        "Стиль как в современных модных журналах."
    )

    frame_lock = (
        "КАДР: по грудь, по пояс или по колено. Ноги ниже колена не видны. "
        "Без обуви. Не делай полный рост. "
    )

    pose_lock = (
        "ПОЗА: естественная, живая, как на реальном фото — не сток. "
        "Руки заняты: кружка какао, ёлочный шар, подарок, гирлянда. "
        "Или рука в кармане, поправляет воротник, облокотился на капот. "
        "Поза — случайный момент, а не позирование. "
        "Живое, тёплое, человеческое фото."
    )

    # ===== РЕАЛИЗМ ИЛИ РИСОВАННЫЙ СТИЛЬ =====
    style_key_pre = state.get("style", "realistic")
    is_art_style = style_key_pre in ("soviet_card", "soviet_fairy", "soviet_cartoon", "disney", "comics")

    if is_art_style:
        realism_lock = ""
        art_style_lock = (
            "ХУДОЖЕСТВЕННЫЙ СТИЛЬ — ЭТО НЕ ФОТОГРАФИЯ. "
            "Изображение должно быть РИСОВАННЫМ, а НЕ фотореалистичным. "
            "НЕ делай фотографию с людьми — сделай ХУДОЖЕСТВЕННУЮ ИЛЛЮСТРАЦИЮ. "
            "Запрещено: фотореализм, кожа с порами, реалистичные детали, эффект камеры. "
            "Нужно: рисованная иллюстрация, стилизация под выбранный стиль. "
        )
        face_realism_lock = ""
        emotion_lock = ""
    else:
        realism_lock = (
            "РЕАЛИЗМ: фото должно выглядеть как настоящий кадр, "
            "а НЕ как рендер нейросети. "
            "ЗАПРЕЩЕНО: слишком гладкая кожа, идеальная симметрия, "
            "кукольные лица, пластиковый рендер, стерильность. "
            "НУЖНО: лёгкая асимметрия, естественные тени, "
            "мягкий рассеянный свет, живая фотография."
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
            "ИНТЕГРАЦИЯ: лицо освещено светом сцены, тени от шапок и шарфов, "
            "тон кожи — из сцены. Лица — ЧАСТЬ кадра, а не аппликация. "
            "Стиль: мягкий свет, лёгкий расфокус по краям, боке от гирлянд, "
            "тёплые оттенки. Лица — в фокусе и узнаваемы."
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
        f"ЛОКАЦИЯ: {location_text}. {sub_text}. "
        "Зимняя атмосфера, снег, тёплый свет, гирлянды. "
    )

    accessories_lock = (
        "УКРАШЕНИЯ: по умолчанию НЕ рисуй никаких украшений. "
        "НЕ рисуй кольца, браслеты, серьги, цепочки, часы. "
        "Если на исходном фото украшений не видно — НЕ добавляй их. "
        "Если видно (кольцо, серьга, цепочка) — сохрани в точности. "
        "ЗАПРЕЩЕНО дорисовывать украшения, которых не видно на исходном."
    )

    atmosphere_lock = (
        "АТМОСФЕРА: новогодняя сказка, тёплая ламповая атмосфера. "
        "Гирлянды с тёплыми огоньками, золотые блики, боке, "
        "мягкий рассеянный свет, тёплые золотистые тона, "
        "лёгкое свечение вокруг огней. "
        "Мягкие тени — НЕ глубокие, НЕ контрастные. "
        "Без плёночной зернистости, без винтажных теней, без резкого контраста. "
        "Атмосферные детали: кружки с какао, печенье, мандарины, "
        "ёлочные шары, подарки, свечи, еловые ветки. "
        "Лёгкий снег в воздухе. Уют и волшебство."
    )

    # ===== ФОРМАТ =====
    from main import get_size_for_format
    fmt_key = state.get("format", "1_1")
    fmt = XMAS_FORMATS.get(fmt_key, XMAS_FORMATS["1_1"])
    photo_bytes = state.get("photo")
    img_size = get_size_for_format(fmt_key, photo_bytes)

    format_lock = (
        f"ФОРМАТ КАДРА: {fmt['name']}, размер {img_size}. "
        f"Построй КРАСИВУЮ ГАРМОНИЧНУЮ композицию под этот формат — {fmt['desc']}. "
        "Кадрирование людей выбери САМ: по грудь, по пояс или по колено — как гармонично смотрится. "
        "Главное — чтобы композиция была ЦЕЛЬНОЙ, БЕЗ пустых полос, БЕЗ обрезов посередине фигуры. "
        f"Верни изображение РОВНО {img_size} пикселей. "
    )

    # ===== СТИЛЬ =====
    style_key = state.get("style", "realistic")
    style = XMAS_STYLES.get(style_key, XMAS_STYLES["realistic"])
    style_lock = style["prompt"] if style["prompt"] else ""

    if is_art_style:
        final_line = "Финальный стиль: рисованная иллюстрация, художественный стиль."
    else:
        final_line = "Финальный стиль: атмосферно, тепло, живо, реалистично, кинематографично."

    full = (
        f"Новогодняя иллюстрация. "
        f"{face_lock}"
        f"{face_realism_lock}"
        f"{emotion_lock}"
        f"{outfit_lock}"
        f"{accessories_lock}"
        f"{frame_lock}"
        f"{pose_lock}"
        f"{location_lock}"
        f"{chorovod_lock}"
        f"{atmosphere_lock}"
        f"{realism_lock}"
        f"{art_style_lock}"
        f"{format_lock}"
        f"{style_lock}"
        f"{final_line} "
        f"Размер: {img_size}."
    )
    return full


async def _generate_and_send(message: Message, user_id: int, state: dict):
    """Генерирует 1 кадр и отправляет. Списывает 1 генерацию."""
    from ai_service import generate_image
    from main import get_balance, spend_generation, test_mode, buy_generations_keyboard

    photo = state.get("photo")
    if not photo:
        await message.answer("❌ Нет фото. Загрузи заново.")
        return

    is_regen = state.get("regen_done", False)

    # При перегенерации — не списываем. При первой генерации — списываем.
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

    logger.info(f"🎨 xmas генерация: user={user_id}, regen={is_regen}")

    try:
        img = generate_image(photo, full_prompt)
        if not img:
            logger.warning("⚠️ xmas: первая попытка не удалась, пробую ещё раз")
            await message.answer("🔄 Сервис задумался, пробую ещё раз...")
            img = generate_image(photo, full_prompt)
    except Exception as e:
        logger.exception(f"❌ xmas: исключение при генерации: {e}")
        img = None

    if not img:
        logger.warning(f"❌ xmas: generate_image вернул None")
        # Если это была перегенерация — сбрасываем флаг, чтобы можно было попробовать снова
        state["regen_done"] = False
        xmas_state[user_id] = state
        await message.answer(
            "😔 Не удалось сгенерировать кадр.\n\n"
            "✅ Попытка НЕ списана.\n"
            "🔄 Нажми «Перегенерировать» ещё раз."
        )
        return

    logger.info(f"✅ xmas: кадр получен")

    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    try:
        await message.answer_photo(
            BufferedInputFile(img, filename="xmas.jpg"),
            caption=f"🎄 <b>Готово!</b>\n\n💎 Баланс: {balance_text}",
            parse_mode="HTML",
            reply_markup=result_keyboard(),
        )
    except Exception as e:
        logger.exception(f"❌ xmas: ошибка отправки фото: {e}")
        await message.answer("❌ Не удалось отправить фото.")
