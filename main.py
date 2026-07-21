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
import json
import io as io_module
from PIL import Image

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    URLInputFile,
)

from config import TELEGRAM_BOT_TOKEN
from ai_service import analyze_photo, generate_image
from image_utils import download_and_resize, image_to_bytes, draw_hints
from stats import add_analysis, get_stats
from course import get_status, add_photo, check_day, has_access, get_day_photos

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

flask_app = Flask(__name__)

user_mode = {}
free_generations = {}
paid_generations = {}
GEN_FILE = "generations.json"
last_photo = {}
gen_wish = {}

def _load_gen():
    global free_generations, paid_generations
    if os.path.exists(GEN_FILE):
        with open(GEN_FILE, "r") as f:
            data = json.load(f)
            free_generations = {int(k): v for k, v in data.get("free", {}).items()}
            paid_generations = {int(k): v for k, v in data.get("paid", {}).items()}

def _save_gen():
    with open(GEN_FILE, "w") as f:
        json.dump({
            "free": {str(k): v for k, v in free_generations.items()},
            "paid": {str(k): v for k, v in paid_generations.items()},
        }, f)

_load_gen()

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

        if amount >= 490 and "курс" in comment.lower():
            from course import activate_by_username
            activate_by_username(telegram_username)

        if amount >= 99 and amount < 249 and "генерац" in comment.lower():
            paid_generations[telegram_username] = paid_generations.get(telegram_username, 0) + 5
            _save_gen()
        elif amount >= 249 and "генерац" in comment.lower():
            paid_generations[telegram_username] = paid_generations.get(telegram_username, 0) + 20
            _save_gen()

        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

DONATE_LOGIN = "1515230"

def get_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []

    free_left = 1 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)

    if user_id == 456504792:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (автор)", callback_data="gen_free")])
    elif free_left > 0:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (1 бесплатно)", callback_data="gen_free")])
    elif paid_left > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото (осталось {paid_left})", callback_data="gen_paid")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 5 улучшений — 99 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=99&comment=генерации")])
        buttons.append([InlineKeyboardButton(text="💛 20 улучшений — 249 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=249&comment=генерации")])

    if has_access(user_id) and user_mode.get(user_id) == "course":
        buttons.append([InlineKeyboardButton(text="📸 Продолжить курс", callback_data="mode_course")])
        buttons.append([InlineKeyboardButton(text="🔍 Просто анализ", callback_data="mode_free")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 Поддержать на 100 ₽", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=100")])
        buttons.append([InlineKeyboardButton(text="💛 Поддержать (любая сумма)", url=f"https://donatepay.ru/don/{DONATE_LOGIN}")])
        buttons.append([InlineKeyboardButton(text="🎓 Мини-курс", callback_data="course_status")])

    buttons.append([InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")])
    buttons.append([InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

AUTHOR_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
    ]
)


async def send_photos(chat_id: int, day: int):
    photos = get_day_photos(day)
    if not photos:
        return
    try:
        if len(photos) == 1:
            await bot.send_photo(chat_id, URLInputFile(photos[0]))
        elif len(photos) >= 2:
            media = [InputMediaPhoto(media=URLInputFile(photos[0]))]
            for url in photos[1:]:
                media.append(InputMediaPhoto(media=URLInputFile(url)))
            await bot.send_media_group(chat_id, media)
    except Exception as e:
        logging.error(f"Ошибка отправки фото: {e}")


@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "👋 Привет! Я — бот-наставник по мобильной фотографии.\n\n"
        "Пришли мне фото, и я найду композиционные ошибки: "
        "заваленный горизонт, мусор в кадре, неудачную позу и другое. "
        "Ты получишь фото с подсказками прямо на нём и короткий разбор от профи. 📸\n\n"
        "✨ <b>Новинка:</b> теперь можно сгенерировать исправленную версию фото с помощью ИИ!",
        reply_markup=AUTHOR_KEYBOARD,
        parse_mode="HTML",
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

@dp.message(Command("free"))
async def handle_free_mode(message: Message):
    user_mode[message.from_user.id] = "free"
    await message.answer("🔍 Режим обычного анализа. Присылай фото — я разберу их без привязки к курсу.")

@dp.message(Command("course"))
async def handle_course(message: Message):
    if has_access(message.from_user.id):
        status = get_status(message.from_user.id)
        if status is not None:
            if "День 0" in status or "Подготовка" in status:
                await message.answer(
                    status,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")],
                        ]
                    ),
                )
                await send_photos(message.chat.id, 0)
            else:
                await message.answer(status, parse_mode="HTML")
                from course import _load_users
                users = _load_users()
                uid = str(message.from_user.id)
                if uid in users:
                    day = users[uid].get("day", 1)
                    await send_photos(message.chat.id, day)
    else:
        await message.answer(
            "🎓 <b>Мини-курс по композиции</b>\n\n"
            "9-дневный челлендж: подготовка, горизонт, правило третей, поза, свет, тень, отражения, фрейминг, ритм и перспектива, глубина кадра.\n\n"
            "Стоимость: 490 ₽.\n\n"
            "<b>Как оплатить и получить доступ:</b>\n"
            "1. Нажми кнопку «Оплатить доступ».\n"
            "2. В комментарии к платежу напиши свой Telegram: <b>@твойник</b> и слово <b>курс</b>\n"
            "3. После оплаты доступ откроется автоматически!\n\n"
            "Напиши /course после оплаты.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💛 Оплатить доступ (490 ₽)", url=f"https://donatepay.ru/don/{DONATE_LOGIN}?sum=490&comment=курс")],
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


@dp.message(Command("start_course"))
async def handle_force_start(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("Только автор.")
        return
    from course import activate_by_username
    activate_by_username("sevosphoto")
    user_mode[message.from_user.id] = "course"
    await message.answer("✅ Курс активирован. Напиши /course или нажми кнопку Мини-курс.")


@dp.callback_query(F.data == "author_info")
async def handle_author_info(callback: CallbackQuery):
    await callback.answer()
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


@dp.callback_query(F.data == "my_stats")
async def handle_stats_button(callback: CallbackQuery):
    await callback.answer()
    text = get_stats(callback.from_user.id)
    await callback.message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data == "course_status")
async def handle_course_status(callback: CallbackQuery):
    await callback.answer()
    if not has_access(callback.from_user.id):
        await callback.message.answer("У тебя нет доступа. Напиши /course чтобы узнать, как оплатить.")
    else:
        user_mode[callback.from_user.id] = "course"
        status = get_status(callback.from_user.id)
        if status is not None:
            if "День 0" in status or "Подготовка" in status:
                await callback.message.answer(
                    status,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")],
                        ]
                    ),
                )
                await send_photos(callback.message.chat.id, 0)
            else:
                await callback.message.answer(status, parse_mode="HTML")
                from course import _load_users
                users = _load_users()
                uid = str(callback.from_user.id)
                if uid in users:
                    day = users[uid].get("day", 1)
                    await send_photos(callback.message.chat.id, day)
        else:
            await callback.message.answer("Произошла ошибка. Напиши /reset для сброса курса.")


@dp.callback_query(F.data == "start_course_btn")
async def handle_start_course_btn(callback: CallbackQuery):
    await callback.answer()
    user_mode[callback.from_user.id] = "course"
    add_text = add_photo(callback.from_user.id)
    if add_text:
        await callback.message.answer(add_text, parse_mode="HTML")
        await send_photos(callback.message.chat.id, 1)


@dp.callback_query(F.data == "mode_course")
async def handle_mode_course(callback: CallbackQuery):
    await callback.answer("✅ Режим курса. Присылай фото для задания.")
    user_id = callback.from_user.id
    user_mode[user_id] = "course"
    status = get_status(user_id)
    if status:
        await callback.message.answer(status, parse_mode="HTML")
        from course import _load_users
        users = _load_users()
        uid = str(user_id)
        if uid in users:
            day = users[uid].get("day", 1)
            await send_photos(callback.message.chat.id, day)


@dp.callback_query(F.data == "mode_free")
async def handle_mode_free(callback: CallbackQuery):
    await callback.answer("🔍 Обычный анализ. Фото не засчитается в курс.")
    user_mode[callback.from_user.id] = "free"


@dp.callback_query(F.data == "new_photo")
async def handle_retry_button(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Присылай следующее фото — жду! 📷")


# ===== ГЕНЕРАЦИЯ =====

@dp.callback_query(F.data == "gen_free")
async def handle_gen_free(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id != 456504792 and free_generations.get(user_id, 0) >= 1:
        await callback.message.answer("Ты уже использовал бесплатную генерацию. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.message.answer("Сначала пришли фото для анализа!")
        return
    await callback.message.answer(
        "✨ <b>Улучшение фото</b>\n\n"
        "Напиши одним сообщением, что улучшить (например: «дорисуй руку, сделай свет теплее»)\n"
        "Или напиши «ок», чтобы просто улучшить.\n\n"
        "ℹ️ Фото будет в формате исходного изображения.",
        parse_mode="HTML",
    )
    user_mode[user_id] = "gen_wish_free"


@dp.callback_query(F.data == "gen_paid")
async def handle_gen_paid(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if paid_generations.get(user_id, 0) <= 0:
        await callback.message.answer("У тебя нет оплаченных генераций. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.message.answer("Сначала пришли фото для анализа!")
        return
    await callback.message.answer(
        "✨ <b>Улучшение фото</b>\n\n"
        "Напиши одним сообщением, что улучшить (например: «дорисуй руку, сделай свет теплее»)\n"
        "Или напиши «ок», чтобы просто улучшить.\n\n"
        "ℹ️ Фото будет в формате исходного изображения.",
        parse_mode="HTML",
    )
    user_mode[user_id] = "gen_wish_paid"


async def do_generation(user_id: int, chat_id: int, gen_type: str):
    if user_id not in last_photo:
        await bot.send_message(chat_id, "Сначала пришли фото для анализа!")
        return

    wish = gen_wish.get(user_id, "")
    await bot.send_message(chat_id, "🎨 Генерирую изображение... Обычно это 30-60 секунд.")

    try:
        image_bytes = last_photo[user_id]

        prompt = f"Улучши это фото: исправь композицию, выровняй горизонт, дорисуй обрезанные края, убери отвлекающие объекты, улучши свет и цвета. Сохрани все важные детали и объекты."
        if wish and wish.lower() != "ок":
            prompt += f" Дополнительное пожелание: {wish}"

        result = generate_image(image_bytes, prompt)

        if result is None:
            await bot.send_message(chat_id, "😕 Не удалось сгенерировать изображение. Попробуй другое фото.")
            return

        try:
            img = Image.open(io_module.BytesIO(result))
            if max(img.size) > 1920:
                img.thumbnail((1920, 1920), Image.LANCZOS)
            buf = io_module.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            result = buf.getvalue()
        except Exception:
            pass

        if gen_type == "free" and user_id != 456504792:
            free_generations[user_id] = 1
            _save_gen()
        elif gen_type == "paid":
            paid_generations[user_id] = max(0, paid_generations.get(user_id, 0) - 1)
            _save_gen()

        await bot.send_photo(
            chat_id,
            BufferedInputFile(result, filename="generated.jpg"),
            caption="✨ Вот твой улучшенный кадр!\n\n"
                    "Если хочешь ещё — купи пакет генераций.",
            reply_markup=get_keyboard(user_id),
        )

    except Exception as e:
        logging.exception("Ошибка генерации")
        await bot.send_message(chat_id, "😕 Что-то пошло не так при генерации. Попробуй ещё раз.")


@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id

    processing_msg = await message.answer("🔍 Анализирую кадр... Обычно до минуты, иногда быстрее.")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file.file_path}"

        image = download_and_resize(photo_url, target_width=1024)
        image_bytes = image_to_bytes(image)

        last_photo[user_id] = image_bytes

        course_topic = None
        if has_access(user_id) and user_mode.get(user_id) == "course":
            from course import get_current_topic
            course_topic = get_current_topic(user_id)

        result = analyze_photo(image_bytes, course_topic=course_topic)

        if result is not None:
            error_type = result.get("error_type", "unknown")
            add_analysis(user_id, error_type)

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
        await message.answer(caption, reply_markup=get_keyboard(user_id))

        if has_access(user_id) and user_mode.get(user_id) == "course":
            status = get_status(user_id)
            if status is not None and "День" in status:
                add_photo(user_id)
                check_text = check_day(user_id, result)
                if check_text:
                    await message.answer(check_text, parse_mode="HTML")
                # Всегда отправляем фото для текущего дня
                from course import _load_users
                users = _load_users()
                uid = str(user_id)
                if uid in users:
                    day = users[uid].get("day", 1)
                    await send_photos(message.chat.id, day)

        await processing_msg.delete()

    except Exception:
        logging.exception("Ошибка при обработке фото")
        await processing_msg.edit_text(
            "😕 Что-то пошло не так при анализе фото. Попробуй ещё раз."
        )


@dp.message(~F.photo)
async def handle_non_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")

    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_wish[user_id] = message.text
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "course" if has_access(user_id) else "free"
        return

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
