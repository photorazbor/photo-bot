"""
Карта дня — мистический ритуал с фотографией.
3 дня подряд бесплатно, потом платно (1 генерация).
"""
import logging
import random
from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logger = logging.getLogger(__name__)

# ===== ТЕМЫ КАРТ =====
DAILY_THEMES = [
    {
        "name": "Изобилие",
        "symbol": "золотые монеты, солнце, рог изобилия, пшеница",
        "predictions": [
            "Сегодня Вселенная открыта для тебя. Всё, что начнёшь — получит поддержку.",
            "Деньги и удача идут к тебе. Принимай с благодарностью.",
            "Твой труд сегодня принесёт плоды. Не сомневайся.",
        ],
        "rituals": [
            "Сфоткай сегодня что-то золотое или жёлтое — солнечный свет, листья, украшение. Это привлечёт удачу. Потом разбери фото через бота — так закрепишь энергию дня.",
            "Найди отражение в луже или окне и сфоткай его. Отражение удваивает изобилие. Разбери кадр — увидишь подсказку.",
            "Сфоткай что-то круглое — монету, солнце, яблоко. Круг — символ бесконечного потока. Улучши фото через бота — усиль энергию.",
        ],
    },
    {
        "name": "Любовь",
        "symbol": "сердце, розы, две птицы, тёплый свет",
        "predictions": [
            "Сегодня сердце открыто. Скажи близким то, что давно хотел.",
            "Тепло вернётся к тебе. Будь мягче с собой.",
            "Любовь рядом — заметь её в мелочах.",
        ],
        "rituals": [
            "Сфоткай что-то красное или розовое — цветок, закат, чашку. Это притянет тепло. Разбери фото — бот подскажет, как улучшить.",
            "Найди симметрию — парные предметы, отражения. Сфоткай их. Симметрия — язык любви. Стилизуй фото в нежном стиле.",
            "Сфоткай тень рядом с собой — она напомнит, что ты не один. Улучши кадр через бота.",
        ],
    },
    {
        "name": "Успех",
        "symbol": "восходящее солнце, гора, стрела вверх",
        "predictions": [
            "Сегодня твои усилия заметят. Говори смело.",
            "Шаг вперёд сейчас важнее идеального плана.",
            "Ты ближе к цели, чем кажется. Продолжай.",
        ],
        "rituals": [
            "Сфоткай что-то, что символизирует движение — дорогу, ступени, стрелку. Разбери фото — увидишь свой путь со стороны.",
            "Сфоткай небо — оно открывает дорогу. Улучши кадр, чтобы усилить намерение.",
            "Найди вертикаль — столб, дерево, здание. Сфоткай её. Вертикаль = рост. Стилизуй в стиле «Кино».",
        ],
    },
    {
        "name": "Здоровье",
        "symbol": "зелёный лист, вода, солнце, тело",
        "predictions": [
            "Сегодня тело просит заботы. Услышь его.",
            "Вода и воздух — твои союзники. Пей больше.",
            "Энергия вернётся, если замедлишься.",
        ],
        "rituals": [
            "Сфоткай что-то зелёное — растение, лист, траву. Это привлечёт здоровье. Разбери фото — бот даст совет по композиции.",
            "Сфоткай воду — реку, чашку, капли. Вода очищает. Улучши фото — усиль эффект.",
            "Сфоткай своё отражение — так ты признаёшь себя. Стилизуй в нежном стиле «Пастель».",
        ],
    },
    {
        "name": "Перемены",
        "symbol": "бабочка, вихрь, распахнутая дверь",
        "predictions": [
            "Что-то уходит — не держи. На его место придёт лучшее.",
            "Сегодня можно начать заново. Прямо сейчас.",
            "Перемены уже начались. Доверься им.",
        ],
        "rituals": [
            "Сфоткай что-то необычное, что выбивается из привычной картины. Это знак перемен. Разбери фото — увидишь, куда идти.",
            "Найди контраст — свет и тень, старое и новое. Сфоткай. Стилизуй в стиле «Комикс» — пусть жизнь станет ярче.",
            "Сфоткай открытую дверь, окно или проход. Это символ нового пути. Улучши кадр.",
        ],
    },
    {
        "name": "Интуиция",
        "symbol": "луна, глаз, звёзды, кристалл",
        "predictions": [
            "Сегодня слушай тишину. Ответ придёт сам.",
            "Твоё тело знает раньше ума. Доверься.",
            "Сон этой ночи — подсказка. Запомни его.",
        ],
        "rituals": [
            "Сфоткай что-то, что привлекло взгляд случайно. Это твоя интуиция. Разбери фото — увидишь послание.",
            "Сфоткай тень — она показывает скрытое. Стилизуй в стиле «Старинная».",
            "Найди отражение луны, света, блика. Сфоткай. Улучши кадр.",
        ],
    },
    {
        "name": "Радость",
        "symbol": "солнце, дети, смех, яркие цвета",
        "predictions": [
            "Сегодня можно быть лёгким. Разреши себе.",
            "Радость рядом — в мелочах, которые ты не замечал.",
            "Улыбнись первому, кого встретишь. Вернётся вдвойне.",
        ],
        "rituals": [
            "Сфоткай что-то яркое — цветок, игрушку, еду. Это усилит радость. Разбери фото — бот похвалит.",
            "Сфоткай что-то смешное или нелепое. Стилизуй в стиле «Ржака-портрет» — будет весело.",
            "Сфоткай себя в зеркале с улыбкой. Улучши кадр — увидишь себя со стороны.",
        ],
    },
    {
        "name": "Страсть",
        "symbol": "огонь, сердце, красный цвет, движение",
        "predictions": [
            "Сегодня твори. Руки знают, что делать.",
            "Страсть — это топливо. Не гаси её.",
            "Сделай то, что давно откладывал. Сейчас время.",
        ],
        "rituals": [
            "Сфоткай что-то огненное — свечу, закат, красный предмет. Это разожжёт страсть. Разбери фото.",
            "Сфоткай движение — бег, танец, ветер. Стилизуй в стиле «Кино» — станет кинематографично.",
            "Найди контраст — свет в темноте. Сфоткай. Улучши кадр — усиль эмоцию.",
        ],
    },
    {
        "name": "Покой",
        "symbol": "тихая вода, лотос, луна, мягкий свет",
        "predictions": [
            "Сегодня не спеши. Тишина даст ответы.",
            "Отпусти то, что не твоё. Дыши.",
            "Покой — это не слабость, а сила.",
        ],
        "rituals": [
            "Сфоткай что-то тихое — воду, туман, мягкий свет. Это успокоит. Разбери фото.",
            "Сфоткай своё дыхание — пар от чая, выдох на стекле. Стилизуй в стиле «Акварель».",
            "Найди симметрию в природе. Сфоткай. Улучши кадр — усилишь гармонию.",
        ],
    },
    {
        "name": "Поток",
        "symbol": "река, ветер, птицы в полёте, волны",
        "predictions": [
            "Сегодня не сопротивляйся. Плыви по течению.",
            "Всё идёт своим чередом. Доверься процессу.",
            "Движение важнее направления.",
        ],
        "rituals": [
            "Сфоткай что-то в движении — облака, воду, ветер. Разбери фото — увидишь ритм.",
            "Сфоткай дорогу или тропу. Стилизуй в стиле «Кино» — почувствуй путь.",
            "Найди ведущие линии — они укажут направление. Улучши кадр.",
        ],
    },
    {
        "name": "Магия",
        "symbol": "звёзды, кристалл, руны, свечение",
        "predictions": [
            "Сегодня возможно невозможное. Загадай.",
            "Мир полон знаков. Замечай их.",
            "Ты — творец своей реальности. Помни.",
        ],
        "rituals": [
            "Сфоткай что-то мерцающее — блик, свечу, украшение. Это усилит магию. Разбери фото.",
            "Найди необычный ракурс — снизу, сверху, боком. Сфоткай. Стилизуй в стиле «Стимпанк».",
            "Сфоткай тень — она скрывает тайное. Улучши кадр — увидишь знак.",
        ],
    },
    {
        "name": "Защита",
        "symbol": "щит, камень, круг, тёплый свет",
        "predictions": [
            "Сегодня ты в безопасности. Верь этому.",
            "Границы — это не стены, а забота о себе.",
            "Никто не может отнять твою силу. Помни.",
        ],
        "rituals": [
            "Сфоткай что-то крепкое — камень, стену, дерево. Это укрепит защиту. Разбери фото.",
            "Сфоткай круг — тарелку, колесо, солнце. Круг = защита. Стилизуй в стиле «Пастель».",
            "Найди тень, которая защищает — от дерева, зонта. Сфоткай. Улучши кадр.",
        ],
    },
    {
        "name": "Ясность",
        "symbol": "глаз, кристалл, чистый свет, зеркало",
        "predictions": [
            "Сегодня ответ придёт сам. Просто спроси.",
            "Туман рассеется. Ты увидишь путь.",
            "Доверяй своему взгляду. Он точен.",
        ],
        "rituals": [
            "Сфоткай что-то прозрачное — стекло, воду, кристалл. Это прояснит ум. Разбери фото.",
            "Найди отражение — в окне, луже, зеркале. Сфоткай. Стилизуй в стиле «Старинная».",
            "Сфоткай горизонт — линию, где встречаются земля и небо. Улучши кадр — выровняй горизонт.",
        ],
    },
    {
        "name": "Рост",
        "symbol": "росток, дерево, ступени, восход",
        "predictions": [
            "Сегодня ты становишься больше. Заметь это.",
            "Маленький шаг — уже рост. Продолжай.",
            "Всё, что ты делаешь, имеет смысл. Даже если не видно.",
        ],
        "rituals": [
            "Сфоткай что-то растущее — растение, ребёнка, себя. Это укрепит рост. Разбери фото.",
            "Найди вертикаль — дерево, столб, ступени. Сфоткай. Стилизуй в стиле «Кино».",
            "Сфоткай восход или утренний свет. Улучши кадр — закрепи намерение.",
        ],
    },
    {
        "name": "Тайна",
        "symbol": "ключ, дверь, туман, звёзды",
        "predictions": [
            "Сегодня что-то скрытое откроется. Будь готов.",
            "Не всё нужно понимать. Иногда просто доверься.",
            "Тайна — это подарок, а не загадка.",
        ],
        "rituals": [
            "Сфоткай что-то загадочное — туман, тень, отражение. Разбери фото — увидишь смысл.",
            "Найди скрытое — деталь, которую не замечают. Сфоткай. Стилизуй в стиле «Готика».",
            "Сфоткай дверь или окно — символ неизвестного. Улучши кадр.",
        ],
    },
]

# ===== СОСТОЯНИЕ =====
daily_state = {}        # {user_id: {"streak": 3, "last_date": "2026-09-21"}}
FREE_DAYS_LIMIT = 3


def _get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_user_state(user_id: int) -> dict:
    if user_id not in daily_state:
        daily_state[user_id] = {"streak": 0, "last_date": None}
    return daily_state[user_id]


def _can_get_free(user_id: int) -> bool:
    """Проверяет, может ли пользователь получить бесплатную карту."""
    state = _get_user_state(user_id)
    today = _get_today()
    if state["last_date"] == today:
        return False  # уже получал сегодня
    if state["streak"] >= FREE_DAYS_LIMIT:
        return False  # лимит исчерпан
    return True


def _was_shown_today(user_id: int) -> bool:
    state = _get_user_state(user_id)
    return state["last_date"] == _get_today()


def _mark_free_used(user_id: int):
    """Отмечает, что пользователь получил бесплатную карту сегодня."""
    state = _get_user_state(user_id)
    today = _get_today()
    if state["last_date"] is None:
        state["streak"] = 1
    elif state["last_date"] != today:
        state["streak"] += 1
    state["last_date"] = today


def _rollback_free(user_id: int):
    """Откат — если карта не сгенерировалась."""
    state = _get_user_state(user_id)
    if state["streak"] > 0:
        state["streak"] -= 1
    state["last_date"] = None


def _reset_state(user_id: int):
    """Полный сброс — для отладки."""
    daily_state.pop(user_id, None)


def reset_daily_state(user_id: int):
    """Сброс состояния карты дня."""
    _reset_state(user_id)


def is_user_in_daily_flow(user_id: int) -> bool:
    return False  # карта дня не требует ожидания фото


# ===== ПРОМПТ =====
def _build_card_prompt(theme: dict, prediction: str) -> str:
    return (
        f"Создай мистическую карту дня в стиле таро, вертикальный формат 9:16. "
        f"Тема карты: {theme['name']}. "
        f"Мистический символ в центре: {theme['symbol']}. "
        f"Стиль: винтажная иллюстрация, глубокие цвета, звёзды, луна, туман, магия. "
        f"Атмосфера: таинственная, вдохновляющая, тёплая. "
        f"ТЕКСТ НА КАРТИНКЕ (на русском, читаемый, красивым шрифтом): "
        f"Вверху карты крупно — название: «{theme['name']}». "
        f"Внизу карты — короткое послание на 2-3 строки: «{prediction}». "
        f"Стиль текста: рукописный или винтажный, как на старинной карте таро. "
        f"Не добавляй лишний текст, только название и послание. "
        f"Без водяных знаков, без подписей, без рамок со словами."
    )


# ===== РЕГИСТРАЦИЯ =====
def register_daily_handlers(dp):
    """Регистрирует обработчики «Карта дня»."""

    @dp.callback_query(F.data == "daily_card")
    async def handle_daily_card(callback: CallbackQuery):
        await callback.answer()
        from main import get_balance, buy_generations_keyboard, test_mode, spend_generation, user_mode

        user_id = callback.from_user.id
        user_mode[user_id] = "daily"

        # Проверка: уже получал сегодня?
        if _was_shown_today(user_id):
            await callback.message.answer(
                "🌙 <b>Ты уже получил карту сегодня.</b>\n\n"
                "Возвращайся завтра — Вселенная подготовит новое послание.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            )
            return

        # Проверка: бесплатный лимит
        is_free = _can_get_free(user_id)

        if is_free:
            await _show_card(callback.message, user_id, is_free=True)
            return

        # Лимит исчерпан — платно
        balance = get_balance(user_id)
        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 <b>Три бесплатные карты дня уже использованы.</b>\n\n"
                "Хочешь продолжить? Пополни баланс — и карта дня будет доступна каждый день.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="show_buy_menu")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                ])
            )
            return

        await callback.message.answer(
            "🔮 <b>Карта дня — платно</b>\n\n"
            "Три бесплатные карты ты уже получил.\n"
            "Стоимость следующей карты: <b>1 генерация</b>.\n\n"
            f"💎 Твой баланс: {balance}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Получить карту (1 ген.)", callback_data="daily_pay")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            ])
        )

    @dp.callback_query(F.data == "daily_pay")
    async def handle_daily_pay(callback: CallbackQuery):
        await callback.answer()
        from main import get_balance, spend_generation, test_mode, buy_generations_keyboard, user_mode

        user_id = callback.from_user.id

        if not (user_id == 456504792 and test_mode):
            if get_balance(user_id) <= 0:
                await callback.message.answer(
                    "💎 Генерации закончились.\n\nПополни баланс:",
                    reply_markup=buy_generations_keyboard()
                )
                return
        if not spend_generation(user_id):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            return

        await _show_card(callback.message, user_id, is_free=False, already_paid=True)


# ===== ПОКАЗ КАРТЫ =====
async def _show_card(message: Message, user_id: int, is_free: bool, already_paid: bool = False):
    """Генерирует и показывает карту дня."""
    from main import get_balance, test_mode, free_generations, paid_generations, _save_gen

    if is_free and not already_paid:
        _mark_free_used(user_id)

    theme = random.choice(DAILY_THEMES)
    prediction = random.choice(theme["predictions"])
    ritual = random.choice(theme["rituals"])

    prompt = _build_card_prompt(theme, prediction)

    wait_msg = await message.answer("🔮 Генерирую твою карту дня... Обычно это занимает до минуты.")

    try:
        from ai_service import generate_image_from_text
        image = generate_image_from_text(prompt)
    except Exception as e:
        logger.exception(f"❌ daily: ошибка генерации: {e}")
        image = None

    if image is None:
        # Откат лимита
        if is_free and not already_paid:
            _rollback_free(user_id)
        # Откат генерации если платная
        if not is_free and already_paid and not (user_id == 456504792 and test_mode):
            free_used = free_generations.get(user_id, 0)
            if free_used > 0:
                free_generations[user_id] = free_used - 1
            else:
                paid_generations[user_id] = paid_generations.get(user_id, 0) + 1
            _save_gen()

        await wait_msg.edit_text(
            "😔 Не удалось создать карту.\n\n"
            "✅ Лимит не потрачен.\n"
            "🔄 Попробуй ещё раз через минуту."
        )
        return

    balance = get_balance(user_id)
    balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

    caption = (
        f"🔮 <b>Карта дня: {theme['name']}</b>\n\n"
        f"✨ <b>Послание:</b>\n{prediction}\n\n"
        f"📸 <b>Ритуал дня:</b>\n{ritual}\n\n"
        f"💎 Баланс: {balance_text}"
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    await message.answer_photo(
        BufferedInputFile(image, filename="daily_card.jpg"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Разобрать фото", callback_data="new_photo")],
            [InlineKeyboardButton(text="🛠 Инструменты", callback_data="tools_menu")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ])
    )
    from main import user_mode
    user_mode[user_id] = "free"
