"""
Фото по референсу (Pinterest-style).
Пользователь загружает референс + своё фото → получает результат
со стилем референса и лицом со своего фото.
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

# ===== СОСТОЯНИЕ =====
ref_photo = {}       # {user_id: bytes} — референс
user_photo_ref = {}  # {user_id: bytes} — фото пользователя
ref_awaiting = {}    # {user_id: "reference" / "user_photo"}


def reset_ref_state(user_id: int):
    """Сброс состояния референса."""
    ref_photo.pop(user_id, None)
    user_photo_ref.pop(user_id, None)
    ref_awaiting.pop(user_id, None)


def is_user_in_ref_flow(user_id: int) -> bool:
    """True, если пользователь в процессе загрузки фото для референса."""
    return user_id in ref_awaiting


# ===== РЕГИСТРАЦИЯ =====
def register_reference_handlers(dp):
    """Регистрирует обработчики «По референсу»."""

    @dp.callback_query(F.data == "ref_style")
    async def handle_ref_style(callback: CallbackQuery):
        await callback.answer()
        from main import get_balance, buy_generations_keyboard, test_mode, user_mode

        user_id = callback.from_user.id
        balance = get_balance(user_id)

        if balance <= 0 and not (user_id == 456504792 and test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            return

        user_mode[user_id] = "ref_style"
        reset_ref_state(user_id)
        ref_awaiting[user_id] = "reference"

        await callback.message.answer(
            "🖼️ <b>Фото по референсу</b>\n\n"
            "Как это работает:\n"
            "1. Ты присылаешь фото-референс (что хочешь получить по стилю) — "
            "например, картинку из Pinterest\n"
            "2. Потом присылаешь своё фото (откуда взять лицо)\n"
            "3. Я переношу стиль референса на твоё лицо\n\n"
            "⚠️ Результат — художественная интерпретация. "
            "100% сходства не гарантируется.\n\n"
            "💰 Стоимость: 1 генерация\n\n"
            "📸 <b>Шаг 1.</b> Пришли фото-референс.",
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "ref_cancel")
    async def handle_ref_cancel(callback: CallbackQuery):
        await callback.answer()
        from main import user_mode
        user_id = callback.from_user.id
        reset_ref_state(user_id)
        user_mode[user_id] = "free"
        await callback.message.answer("❌ Отменено. Возврат в главное меню.")


# ===== ОБРАБОТКА ФОТО =====
async def handle_reference_photo(message: Message, user_id: int, image_bytes: bytes) -> bool:
    """
    Вызывается из main.handle_photo, если пользователь в ref_awaiting.
    Возвращает True, если фото обработано здесь.
    """
    step = ref_awaiting.get(user_id)
    if not step:
        return False

    from main import user_mode

    if step == "reference":
        ref_photo[user_id] = image_bytes
        ref_awaiting[user_id] = "user_photo"
        await message.answer(
            "✅ Референс получен.\n\n"
            "📸 <b>Шаг 2.</b> Теперь пришли своё фото — "
            "откуда взять лицо.",
            parse_mode="HTML"
        )
        return True

    if step == "user_photo":
        user_photo_ref[user_id] = image_bytes
        reference_bytes = ref_photo.get(user_id)
        user_photo_bytes = user_photo_ref.get(user_id)

        ref_awaiting.pop(user_id, None)

        if not reference_bytes or not user_photo_bytes:
            await message.answer("❌ Что-то потерялось. Начни заново: /start")
            reset_ref_state(user_id)
            user_mode[user_id] = "free"
            return True

        # Проверка баланса и списание
        from main import get_balance, spend_generation, buy_generations_keyboard, test_mode
        if not (user_id == 456504792 and test_mode):
            if get_balance(user_id) <= 0:
                await message.answer(
                    "💎 Генерации закончились.\n\nПополни баланс:",
                    reply_markup=buy_generations_keyboard()
                )
                reset_ref_state(user_id)
                user_mode[user_id] = "free"
                return True
        if not spend_generation(user_id):
            await message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=buy_generations_keyboard()
            )
            reset_ref_state(user_id)
            user_mode[user_id] = "free"
            return True

        await message.answer("🎨 Генерирую по референсу... Это может занять до минуты.")

        prompt = (
            "ВАЖНО: у тебя ДВА изображения. "
            "ПЕРВОЕ — референс (образец стиля, сцены, света, атмосферы). "
            "ВТОРОЕ — фото реального человека (откуда берём ЛИЦО). "
            "\n\n"
            "ЗАДАЧА: создать ОДНО изображение, где человек со ВТОРОГО фото "
            "находится в сцене ПЕРВОГО (референса). "
            "Лицо, внешность и личность — со ВТОРОГО фото. "
            "Всё остальное (свет, фон, поза, одежда, атмосфера, цвет) — с ПЕРВОГО. "
            "\n\n"
            "ЖЁСТКОЕ ПРАВИЛО ПО ЛИЦУ — СОХРАНИТЬ ЛИЦО СО ВТОРОГО ФОТО: "
            "СОХРАНИ черты лица человека со ВТОРОГО фото в ТОЧНОСТИ: "
            "форма лица, овал, лоб, брови (форма, толщина, цвет), "
            "глаза (форма, разрез, цвет), нос (форма, размер), "
            "губы (форма, толщина), подбородок, уши, "
            "веснушки или их отсутствие, родинки, морщины, "
            "цвет волос, причёску, длину волос, "
            "пол, возраст, телосложение, тон кожи. "
            "\n\n"
            "ЗАПРЕЩЕНО: "
            "копировать лицо, брови, глаза, нос, губы, веснушки, родинки, "
            "причёску или цвет волос с ПЕРВОГО изображения (референса). "
            "НЕ добавляй веснушки, если их нет на ВТОРОМ фото. "
            "НЕ делай брови гуще или темнее, чем на ВТОРОМ фото. "
            "НЕ меняй цвет глаз — только со ВТОРОГО фото. "
            "НЕ меняй форму носа, губ, овал лица — только со ВТОРОГО фото. "
            "НЕ старь и НЕ молоди человека. "
            "НЕ меняй пол и национальность. "
            "\n\n"
            "РАЗРЕШЕНО брать с референса: "
            "стиль съёмки, свет, цветовую гамму, атмосферу, "
            "фон, композицию, позу, ракурс, "
            "одежду (если она не мешает узнаваемости лица), "
            "аксессуары, декор, настроение кадра. "
            "\n\n"
            "РЕЗУЛЬТАТ: одно изображение — как будто человек со ВТОРОГО фото "
            "реально снялся в этой фотосессии по референсу. "
            "Лицо — узнаваемое, точное, со ВТОРОГО фото. "
            "Атмосфера — точная, как на референсе. "
            "Кожа естественная, без пластика, с лёгкой текстурой."
        )

        try:
            from ai_service import generate_image_with_reference
            result = generate_image_with_reference(reference_bytes, user_photo_bytes, prompt)
        except Exception as e:
            logger.exception(f"❌ ref_style: ошибка генерации: {e}")
            result = None

        if result is None:
            await message.answer(
                "😔 Не удалось сгенерировать.\n\n"
                "✅ Генерация НЕ списана.\n"
                "🔄 Попробуй ещё раз: /start → Инструменты → По референсу"
            )
            # Вернуть баланс
            if not (user_id == 456504792 and test_mode):
                from main import free_generations, paid_generations, _save_gen
                free_used = free_generations.get(user_id, 0)
                if free_used > 0:
                    free_generations[user_id] = free_used - 1
                else:
                    paid_generations[user_id] = paid_generations.get(user_id, 0) + 1
                _save_gen()
            reset_ref_state(user_id)
            user_mode[user_id] = "free"
            return True

        balance = get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and test_mode) else str(balance)

        await message.answer_photo(
            BufferedInputFile(result, filename="ref_style.jpg"),
            caption=f"🖼️ Готово!\n\n💎 Баланс: {balance_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼️ Ещё по референсу", callback_data="ref_style")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            ])
        )
        reset_ref_state(user_id)
        user_mode[user_id] = "free"
        return True

    return False
