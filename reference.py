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

        wait_msg = await message.answer("🎨 Изучаю референс и генерирую фото... Это может занять до минуты.")

        # Шаг 1: анализ референса (внутренний, пользователь не видит)
        try:
            from ai_service import analyze_reference
            scene_description = analyze_reference(reference_bytes)
        except Exception as e:
            logger.exception(f"❌ ref_style: ошибка анализа референса: {e}")
            scene_description = None

        if not scene_description:
            await wait_msg.edit_text(
                "😔 Не удалось разобрать референс.\n\n"
                "✅ Генерация НЕ списана.\n"
                "🔄 Попробуй другое фото-референс."
            )
            # Вернуть генерацию
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

        logger.info(f"🔍 ref_style: описание референса = {scene_description[:200]}")

        # Шаг 2: генерация по описанию + фото пользователя
        prompt = (
            "Создай фотографию человека со ВТОРОГО изображения "
            "(ВТОРОЕ — фото реального человека). "
            "\n\n"
            f"СЦЕНА (взято с референса):\n{scene_description}\n\n"
            "ВАЖНО — ЧЕЛОВЕК ЦЕЛЬНЫЙ, ЕДИНЫЙ: "
            "Лицо, тело, руки, кожа — это ОДИН человек со ВТОРОГО фото. "
            "Единый тон кожи на лице, шее и руках. "
            "Руки — этого же человека. "
            "\n\n"
            "ЛИЦО — ТОЛЬКО СО ВТОРОГО ФОТО: "
            "СОХРАНИ в точности форму лица, овал, брови (форма, толщина, цвет), "
            "глаза (форма, разрез, цвет), нос, губы, подбородок, "
            "веснушки (или их отсутствие), родинки, "
            "причёску, цвет волос, "
            "пол, возраст, тон кожи. "
            "НЕ копируй лицо, брови, глаза, нос, губы, веснушки, причёску "
            "с референса. "
            "НЕ добавляй веснушки, если их нет на ВТОРОМ фото. "
            "НЕ меняй брови, глаза, нос, губы, овал — только со ВТОРОГО. "
            "НЕ старь и НЕ молоди. "
            "\n\n"
            "СВЕТ, ПОЗА, ФОН, ОДЕЖДА, АТМОСФЕРА — как в описании сцены выше. "
            "Свет падает на лицо так же, как на любого человека в этой сцене. "
            "Тени от предметов (шляпа, рука) падают на лицо естественно. "
            "Лицо — ЧАСТЬ сцены, а не наложенный портрет. "
            "Результат — ОДНА настоящая фотография, а не коллаж."
        )

        try:
            from ai_service import generate_image
            result = generate_image(user_photo_bytes, prompt)
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
