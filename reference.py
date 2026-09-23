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
def _compress_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """Сжимает картинку до max_size по длинной стороне, качество 85."""
    try:
        from PIL import Image as _Img
        import io as _io
        im = _Img.open(_io.BytesIO(image_bytes))
        if max(im.size) > max_size:
            im.thumbnail((max_size, max_size), _Img.LANCZOS)
        buf = _io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"⚠️ ref_style: не удалось сжать картинку: {e}")
        return image_bytes
        
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
        ref_photo[user_id] = _compress_image(image_bytes)
        ref_awaiting[user_id] = "user_photo"
        await message.answer(
            "✅ Референс получен.\n\n"
            "📸 <b>Шаг 2.</b> Теперь пришли своё фото — "
            "откуда взять лицо.",
            parse_mode="HTML"
        )
        return True

    if step == "user_photo":
        user_photo_ref[user_id] = _compress_image(image_bytes)
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

        await message.answer("🎨 Генерирую по референсу... Это может занять до 2 минут.")

        prompt = (
            "Два изображения: "
            "ПЕРВОЕ — референс (образец сцены, позы, света, стиля). "
            "ВТОРОЕ — фото реального человека (образец внешности). "
            "\n\n"
            "ЗАДАЧА: создать ОДНО изображение — человек со ВТОРОГО фото "
            "в сцене ПЕРВОГО. Как будто этот человек сам встал "
            "в эту позу и снялся в этой фотосессии."
            "\n\n"
            "ВНЕШНОСТЬ ЧЕЛОВЕКА — ЦЕЛИКОМ СО ВТОРОГО ФОТО: "
            "лицо, форма лица, брови, глаза (цвет и разрез), нос, губы, "
            "веснушки или их отсутствие, родинки, "
            "причёска, цвет и длина волос, "
            "тон кожи, пол, возраст. "
            "НЕ копируй лицо, брови, глаза, веснушки, родинки, причёску "
            "или тон кожи с ПЕРВОГО фото. "
            "НЕ добавляй веснушки, если их нет на ВТОРОМ. "
            "НЕ меняй брови, глаза, нос, губы, овал — только со ВТОРОГО."
            "\n\n"
            "ТЕЛО И ПРОПОРЦИИ — ЕСТЕСТВЕННЫЕ, ПРОПОРЦИОНАЛЬНЫЕ ЛИЦУ: "
            "Если на ВТОРОМ фото только лицо или по грудь — "
            "сгенерируй тело самостоятельно, соблюдая "
            "естественные анатомические пропорции человеческого тела: "
            "голова → шея → плечи → корпус → руки → ноги. "
            "НЕ растягивай лицо под чужое тело. "
            "НЕ копируй тело с референса буквально. "
            "Создай тело, которое ГАРМОНИЧНО подходит к лицу со ВТОРОГО фото "
            "и соответствует пропорциям взрослого человека. "
            "Руки, шея, тело — единый тон кожи с лицом."
            "\n\n"
            "ПОЗА, СВЕТ, ФОН, ОДЕЖДА — С ПЕРВОГО ФОТО: "
            "положение корпуса, рук, ног — как на референсе. "
            "Ракурс, кадрирование, фон, обстановка — как на референсе. "
            "Свет — точно как на референсе: направление источника, "
            "жёсткость, цвет, направление теней. "
            "Одежда и аксессуары — как на референсе. "
            "Атмосфера, цветовая гамма, тонирование — как на референсе."
            "\n\n"
            "ЕДИНСТВО: "
            "Лицо, шея, руки, тело — единое целое, один свет, один тон кожи. "
            "Лицо освещено светом сцены — как падал бы свет "
            "на любого человека в этой позе. "
            "Тени от предметов (шляпа, рука) падают на лицо естественно. "
            "Руки — этого же человека, тон кожи совпадает с лицом. "
            "Результат — ОДНА настоящая фотография, а не коллаж."
        )

        try:
            from ai_service import generate_image_with_reference
            result = generate_image_with_reference(reference_bytes, user_photo_bytes, prompt)
            if not result:
                logger.warning("⚠️ ref_style: первая попытка не удалась, пробую ещё раз")
                await message.answer("🔄 Сервис задумался, пробую ещё раз...")
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
