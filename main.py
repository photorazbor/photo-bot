"""
Точка входа: Telegram-бот на aiogram 3, который принимает фото
и возвращает разбор композиции с подсказками, нарисованными поверх снимка.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import TELEGRAM_BOT_TOKEN
from ai_service import analyze_photo
from image_utils import download_and_resize, image_to_bytes, draw_hints

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

RETRY_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")]
    ]
)


@dp.message(CommandStart())
async def handle_start(message: Message):
    """Приветственное сообщение по команде /start."""
    await message.answer(
        "👋 Привет! Я — бот-наставник по мобильной фотографии.\n\n"
        "Пришли мне фото, и я найду композиционные ошибки: "
        "заваленный горизонт, мусор в кадре, неудачную позу и другое. "
        "Ты получишь фото с подсказками прямо на нём и короткий разбор от профи. 📸"
    )


@dp.callback_query(F.data == "new_photo")
async def handle_retry_button(callback: CallbackQuery):
    """Обработка нажатия кнопки «Разобрать другое фото»."""
    await callback.message.answer("Присылай следующее фото — жду! 📷")
    await callback.answer()


@dp.message(F.photo)
async def handle_photo(message: Message):
    """Основной обработчик: получает фото, анализирует и отвечает."""
    processing_msg = await message.answer("🔍 Анализирую кадр... Обычно до минуты, иногда быстрее.")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"

        image = download_and_resize(photo_url, target_width=1024)
        image_bytes = image_to_bytes(image)

        result = analyze_photo(image_bytes)

        if result is None:
            await processing_msg.edit_text("😕 Не смог разобрать, попробуй другое фото.")
            return

        drawings = result.get("drawings", [])
        annotated_image = draw_hints(image, drawings)
        annotated_bytes = image_to_bytes(annotated_image)

        await message.answer_photo(
            BufferedInputFile(annotated_bytes, filename="analysis.jpg")
        )

        caption = (
            f"📸 {result.get('title', 'Разбор кадра')}\n\n"
            f"❌ Что не так: {result.get('what_is_wrong', '—')}\n\n"
            f"🔄 Как исправить: {result.get('how_to_fix', '—')}\n\n"
            f"✨ Совет от профи: {result.get('pro_tip', '—')}\n\n"
            f"👍 Что хорошо: {result.get('praise', '—')}\n\n"
            f"🔴 проблема\n"
            f"🟢 правильно\n"
            f"🟡 обрати внимание"
        )
        await message.answer(caption, reply_markup=RETRY_KEYBOARD)

        await processing_msg.delete()

    except Exception:
        logging.exception("Ошибка при обработке фото")
        await processing_msg.edit_text(
            "😕 Что-то пошло не так при анализе фото. Попробуй ещё раз."
        )


@dp.message(~F.photo)
async def handle_non_photo(message: Message):
    """Вежливый ответ, если прислали не фото."""
    await message.answer(
        "Пришли мне, пожалуйста, фотографию 📷 — я умею разбирать только изображения."
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())