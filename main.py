"""
Точка входа: Telegram-бот на aiogram 3 + заглушка для Render + webhook DonatePay
"""
import asyncio
import logging
from threading import Thread
from flask import Flask, request
import os
import hashlib
import hmac
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
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
from stats import add_analysis, get_stats
from course import start_course, get_status, add_photo, check_day, has_access

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running"

@flask_app.route('/donate-webhook', methods=['POST'])
def donate_webhook():
    API_KEY = "pytBdeWXxqGPKL0PW5jLL2QdKCLfDjSiL614W0bZbMehtBMSA7VhE31ylqRE"

    body = request.get_data().decode('utf-8')
    signature = request.headers.get('X-DonatePay-Signature', '')
    expected = hashlib.sha256((body + API_KEY).encode()).hexdigest()

    if signature != expected:
        return 'Invalid signature', 403

    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        comment = data.get('comment', '')
        nickname = data.get('nickname', '')

        match = re.search(r'@(\w+)', comment)
        if not match:
            telegram_username = nickname
        else:
            telegram_username = match.group(1)

        if amount >= 990 and telegram_username:
            from course import activate_by_username
            activate_by_username(telegram_username)

        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

DONATE_LOGIN = "1515230"

DONATE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💛 Поддержать на 100 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=100")],
        [InlineKeyboardButton(text="💛 Поддержать (любая сумма)", url=f"https://donatepay.ru/don/{DONATE_LOGIN}")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")],
        [InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")],
    ]
)

AUTHOR_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
    ]
)


@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "👋 Привет! Я — бот-наставник по мобильной фотографии.\n\n"
        "Пришли мне фото, и я найду композиционные ошибки: "
        "заваленный горизонт, мусор в кадре, неудачную позу и другое. "
        "Ты получишь фото с подсказками прямо на нём и короткий разбор от профи. 📸",
        reply_markup=AUTHOR_KEYBOARD,
    )


@dp.message(Command("author"))
async def handle_author(message: Message):
    await message.answer(
        "📸 <b>Автор бота — Евгений Севостьянов</b>\n"
        "Фотограф, преподаватель мобильной фотографии.\n\n"
        "📷 Instagram: <a href='https://instagram.com/sevosphoto'>@sevosphoto</a>\n"
        "💬 Telegram: <a href='https://t.me/sevosphoto'>@sevosphoto</a>\n"
        "🌐 VK: <a href='https://vk.com/cevoc'>@cevoc</a>\n\n"
        "По вопросам сотрудничества и обучения — пишите в личные сообщения!",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@dp.message(Command("stats"))
async def handle_stats(message: Message):
    text = get_stats(message.from_user.id)
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("course"))
async def handle_course(message: Message):
    if has_access(message.from_user.id):
        status = get_status(message.from_user.id)
        await message.answer(status, parse_mode="HTML")
    else:
        await message.answer(
            "🎓 <b>Мини-курс по композиции</b>\n\n"
            "8-дневный челлендж: подготовка, горизонт, правило третей, поза, свет, тень, отражения, фрейминг.\n\n"
            "Стоимость: 990 ₽.\n\n"
            "<b>Как оплатить и получить доступ:</b>\n"
            "1. Нажми кнопку «Оплатить доступ».\n"
            "2. В комментарии к платежу напиши свой Telegram: <b>@твойник</b>\n"
            "3. После оплаты доступ откроется автоматически!\n\n"
            "Напиши /course после оплаты.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💛 Оплатить доступ (990 ₽)", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=990")],
                ]
            ),
        )


@dp.message(Command("reset"))
async def handle_reset(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("Только автор может сбрасывать курс.")
        return
    if os.path.exists("course_users.json"):
        os.remove("course_users.json")
        await message.answer("✅ Данные курса сброшены. Можешь начинать заново.")
    else:
        await message.answer("Файл уже отсутствует.")


@dp.callback_query(F.data == "author_info")
async def handle_author_info(callback: CallbackQuery):
    await callback.message.answer(
        "📸 <b>Автор бота — Евгений Севостьянов</b>\n"
        "Фотограф, преподаватель мобильной фотографии.\n\n"
        "📷 Instagram: <a href='https://instagram.com/sevosphoto'>@sevosphoto</a>\n"
        "💬 Telegram: <a href='https://t.me/sevosphoto'>@sevosphoto</a>\n"
        "🌐 VK: <a href='https://vk.com/cevoc'>@cevoc</a>\n\n"
        "По вопросам сотрудничества и обучения — пишите в личные сообщения!",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@dp.callback_query(F.data == "my_stats")
async def handle_stats_button(callback: CallbackQuery):
    text = get_stats(callback.from_user.id)
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "course_status")
async def handle_course_status(callback: CallbackQuery):
    await callback.answer()
    if not has_access(callback.from_user.id):
        await callback.message.answer("У тебя нет доступа. Напиши /course чтобы узнать, как оплатить.")
    else:
        status = get_status(callback.from_user.id)
        if status is not None:
            await callback.message.answer(status, parse_mode="HTML")
        else:
            await callback.message.answer("Произошла ошибка. Напиши /reset для сброса курса.")


@dp.callback_query(F.data == "new_photo")
async def handle_retry_button(callback: CallbackQuery):
    await callback.message.answer("Присылай следующее фото — жду! 📷")
    await callback.answer()


@dp.message(F.photo)
async def handle_photo(message: Message):
    processing_msg = await message.answer("🔍 Анализирую кадр... Обычно до минуты, иногда быстрее.")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"

        image = download_and_resize(photo_url, target_width=1024)
        image_bytes = image_to_bytes(image)

        result = analyze_photo(image_bytes)

        if result is not None:
            error_type = result.get("error_type", "unknown")
            add_analysis(message.from_user.id, error_type)

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
            f"🔴 красный — проблема\n"
            f"🟢 зелёный — правильно\n"
            f"🟡 жёлтый — внимание"
        )
        await message.answer(caption, reply_markup=DONATE_KEYBOARD)

        # Проверка курса
        if has_access(message.from_user.id):
            status = get_status(message.from_user.id)
            if status is not None and "День" in status:
                add_text = add_photo(message.from_user.id)
                if add_text:
                    await message.answer(add_text)
                if "проверки" in add_text:
                    check_text = check_day(message.from_user.id, result)
                    if check_text:
                        await message.answer(check_text, parse_mode="HTML")

        await processing_msg.delete()

    except Exception:
        logging.exception("Ошибка при обработке фото")
        await processing_msg.edit_text(
            "😕 Что-то пошло не так при анализе фото. Попробуй ещё раз."
        )


@dp.message(~F.photo)
async def handle_non_photo(message: Message):
    await message.answer(
        "Пришли мне, пожалуйста, фотографию 📷 — я умею разбирать только изображения."
    )


async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
