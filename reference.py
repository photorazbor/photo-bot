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


BASE_REF = "https://raw.githubusercontent.com/photorazbor/photo-bot/main/examples"

# ===== СОСТОЯНИЕ =====
ref_photo = {}
user_photo_ref = {}
ref_awaiting = {}
ref_examples_shown = {}


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
        import main as _main

        user_id = callback.from_user.id
        balance = _main.get_balance(user_id)

        if balance <= 0 and not (user_id == 456504792 and _main.test_mode):
            await callback.message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=_main.buy_generations_keyboard()
            )
            return

        _main.user_mode[user_id] = "ref_style"
        reset_ref_state(user_id)
        ref_awaiting[user_id] = "reference"

        # Показываем примеры коллажей — только раз в день
        from datetime import datetime as _dt
        today = _dt.now().strftime("%Y-%m-%d")
        if ref_examples_shown.get(user_id) != today:
            for idx in (1, 2, 3):
                example_bytes = _fetch_image(f"{BASE_REF}/ref_style/example_{idx}.jpg")
                if not example_bytes:
                    continue
                try:
                    await callback.message.answer_photo(
                        BufferedInputFile(example_bytes, filename=f"example_{idx}.jpg"),
                        caption="✨ <b>Pinterest + фото → результат</b>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка отправки example_{idx}.jpg: {e}")
            ref_examples_shown[user_id] = today

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
        import main as _main
        user_id = callback.from_user.id
        reset_ref_state(user_id)
        _main.user_mode[user_id] = "free"
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

    import main as _main

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
            _main.user_mode[user_id] = "free"
            return True

        # Проверка баланса и списание
        if not (user_id == 456504792 and _main.test_mode):
            if _main.get_balance(user_id) <= 0:
                await message.answer(
                    "💎 Генерации закончились.\n\nПополни баланс:",
                    reply_markup=_main.buy_generations_keyboard()
                )
                reset_ref_state(user_id)
                _main.user_mode[user_id] = "free"
                return True
        if not _main.spend_generation(user_id):
            await message.answer(
                "💎 Генерации закончились.\n\nПополни баланс:",
                reply_markup=_main.buy_generations_keyboard()
            )
            reset_ref_state(user_id)
            _main.user_mode[user_id] = "free"
            return True

        await message.answer("🎨 Генерирую по референсу... Это может занять до 2 минут.")

        prompt = (
            "Два изображения:\n"
            "ФОТО 1 — референс: сцена, фон, свет, атмосфера, тонирование.\n"
            "ФОТО 2 — человек: лицо, черты, пол, возраст.\n\n"
            "Создай ОДНУ гармоничную фотографию:\n"
            "• Сцена, фон, свет, тонирование — из ФОТО 1.\n"
            "• Лицо и черты — из ФОТО 2, но адаптированы под свет и ракурс сцены.\n"
            "• Поза — примерно как на ФОТО 1, но подстроена под человека с ФОТО 2.\n"
            "• Тело, шея, руки — единый тон кожи с лицом.\n"
            "• Построй тело под лицо, а не копируй тело с референса буквально.\n"
            "• Если поза или тело с ФОТО 1 не подходят лицу с ФОТО 2 — "
            "адаптируй их, чтобы результат был гармоничным.\n"
            "• Одежда — как на ФОТО 1.\n"
            "• Аксессуары (очки, украшения, шарфы) — если на ФОТО 1 "
            "они часть образа — используй с ФОТО 1. Если у человека "
            "на ФОТО 2 свои узнаваемые аксессуары — сохрани их.\n\n"
            "СПЕЦЭФФЕКТЫ (СТРОГОЕ ПРАВИЛО):\n"
            "• Внимательно посмотри на ФОТО 1. Есть ли там вода, дым, снег, "
            "огонь, пар, световые лучи?\n"
            "• ЕСЛИ НА ФОТО 1 НЕТ СПЕЦЭФФЕКТОВ — НЕ ДОБАВЛЯЙ ИХ. "
            "Никакой воды, никакого дыма, никаких брызг и потёков. "
            "Сцена — как на ФОТО 1, без лишних эффектов.\n"
            "• ЕСЛИ НА ФОТО 1 ЕСТЬ СПЕЦЭФФЕКТ — наложи ТОЛЬКО ТОТ эффект, "
            "который есть. Вода — только вода, дым — только дым. "
            "НЕ смешивай эффекты, НЕ добавляй то, чего нет на референсе.\n"
            "• Эффект взаимодействует с человеком: "
            "вода течёт ПО лицу, волосам, одежде; капли на коже и тканях; "
            "дым окутывает человека; снег ложится на плечи и волосы. "
            "Лицо остаётся видимым и узнаваемым.\n"
            "• Вода течёт вниз, дым поднимается, снег падает — как в жизни.\n"
            "• Если эффект не получается — упрости его, но сохрани лицо.\n\n"
            "Результат — одна цельная фотография, а не коллаж.\n"
            "Лицо, шея, руки, тело — единое целое, один свет, один тон кожи.\n"
            "НЕ добавляй новых людей. НЕ убирай никого.\n"
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
            if not (user_id == 456504792 and _main.test_mode):
                free_used = _main.free_generations.get(user_id, 0)
                if free_used > 0:
                    _main.free_generations[user_id] = free_used - 1
                else:
                    _main.paid_generations[user_id] = _main.paid_generations.get(user_id, 0) + 1
                _main._save_gen()
            reset_ref_state(user_id)
            _main.user_mode[user_id] = "free"
            return True

        balance = _main.get_balance(user_id)
        balance_text = "∞" if (user_id == 456504792 and _main.test_mode) else str(balance)

        await message.answer_photo(
            BufferedInputFile(result, filename="ref_style.jpg"),
            caption=f"🖼️ Готово!\n\n💎 Баланс: {balance_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼️ Ещё по референсу", callback_data="ref_style")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            ])
        )
        reset_ref_state(user_id)
        _main.user_mode[user_id] = "free"
        return True
