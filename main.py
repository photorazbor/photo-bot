"""
Точка входа: Telegram-бот на aiogram 3 + заглушка для Render
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
from datetime import datetime

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
from ai_service import analyze_photo, generate_image, create_payment_link
from image_utils import download_and_resize, image_to_bytes, draw_hints
from stats import add_analysis, get_stats
from course import get_status, add_photo, check_day, has_access, get_day_photos, _load_users, activate_free_trial

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

flask_app = Flask(__name__)

# ===== ХРАНИЛИЩА ДАННЫХ =====
user_mode = {}
free_generations = {}
paid_generations = {}
GEN_FILE = "generations.json"
last_photo = {}
gen_wish = {}
gen_format = {}
test_mode = False

HISTORY_FILE = "history.json"

def _load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_history(history: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def _add_history(user_id: int, action: str, details: str = ""):
    history = _load_history()
    uid = str(user_id)
    if uid not in history:
        history[uid] = []
    history[uid].append({
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "action": action,
        "details": details
    })
    if len(history[uid]) > 100:
        history[uid] = history[uid][-100:]
    _save_history(history)

# ===== ГЕНЕРАЦИИ =====
SIZE_MAP = {
    "1:1": "1024x1024",
    "3:4": "768x1024",
    "4:3": "1024x768",
    "4:5": "896x1080",
    "16:9": "1280x720",
    "9:16": "720x1280",
}

FORMATS = [
    ("original", "📐 Исходный формат"),
    ("1_1", "📱 1:1 (квадрат)"),
    ("3_4", "📱 3:4 (вертикаль)"),
    ("4_3", "🖼️ 4:3 (горизонт)"),
    ("4_5", "📱 4:5 (Instagram)"),
    ("16_9", "🖼️ 16:9 (панорама)"),
    ("9_16", "📱 9:16 (сториз)"),
]

def get_size_for_format(fmt: str, image_bytes: bytes = None) -> str:
    if fmt == "original" and image_bytes:
        try:
            img = Image.open(io_module.BytesIO(image_bytes))
            w, h = img.size
            w = max(512, (w // 64) * 64)
            h = max(512, (h // 64) * 64)
            return f"{w}x{h}"
        except Exception:
            pass
    key = fmt.replace("_", ":")
    return SIZE_MAP.get(key, "1024x1024")


def format_keyboard(gen_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"gen_{fmt}_{gen_type}")]
        for fmt, name in FORMATS
    ])


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

# ===== FLASK =====
@flask_app.route('/')
def home():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ===== КЛАВИАТУРЫ =====
def donate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💛 100 ₽", callback_data="donate_100"),
            InlineKeyboardButton(text="💛 300 ₽", callback_data="donate_300"),
            InlineKeyboardButton(text="💛 500 ₽", callback_data="donate_500"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="new_photo")],
    ])

def get_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []

    free_left = 1 - free_generations.get(user_id, 0)
    paid_left = paid_generations.get(user_id, 0)

    if user_id == 456504792 and not test_mode:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (автор)", callback_data="gen_free")])
    elif free_left > 0:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить фото (1 бесплатно)", callback_data="gen_free")])
    elif paid_left > 0:
        buttons.append([InlineKeyboardButton(text=f"✨ Улучшить фото (осталось {paid_left})", callback_data="gen_paid")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 5 улучшений — 99 ₽", callback_data="buy_5_gen")])
        buttons.append([InlineKeyboardButton(text="💛 20 улучшений — 249 ₽", callback_data="buy_20_gen")])

    if has_access(user_id) and user_mode.get(user_id) == "course" and not test_mode:
        buttons.append([InlineKeyboardButton(text="📸 Продолжить курс", callback_data="mode_course")])
        buttons.append([InlineKeyboardButton(text="🔍 Просто анализ", callback_data="mode_free")])
    else:
        buttons.append([InlineKeyboardButton(text="💛 Поддержать проект", callback_data="donate_menu")])
        buttons.append([InlineKeyboardButton(text="🎓 Мини-курс по композиции (490 ₽)", callback_data="course_status")])

    buttons.append([InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")])
    buttons.append([InlineKeyboardButton(text="📷 Разобрать другое фото", callback_data="new_photo")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

AUTHOR_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👤 Об авторе", callback_data="author_info")],
    ]
)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
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

async def do_generation(user_id: int, chat_id: int, gen_type: str):
    if user_id not in last_photo:
        await bot.send_message(chat_id, "Сначала пришли фото для анализа!")
        return

    fmt = gen_format.get(user_id, "1_1")
    wish = gen_wish.get(user_id, "")
    image_bytes = last_photo[user_id]

    await bot.send_message(chat_id, "🎨 Генерирую изображение... Обычно это 30-60 секунд.")

    try:
        img_size = get_size_for_format(fmt, image_bytes)

        prompt = f"Улучши это фото: исправь композицию, выровняй горизонт, дорисуй обрезанные края, убери отвлекающие объекты, улучши свет и цвета. Сохрани все важные детали и объекты. Размер: {img_size}."
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

        if gen_type == "free" and not (user_id == 456504792 and not test_mode):
            free_generations[user_id] = 1
            _save_gen()
        elif gen_type == "paid":
            paid_generations[user_id] = max(0, paid_generations.get(user_id, 0) - 1)
            _save_gen()

        format_name = dict(FORMATS).get(fmt, fmt)
        await bot.send_photo(
            chat_id,
            BufferedInputFile(result, filename="generated.jpg"),
            caption=f"✨ Вот твой улучшенный кадр!\nФормат: {format_name}\n\nЕсли хочешь ещё — купи пакет генераций.",
            reply_markup=get_keyboard(user_id),
        )

    except Exception as e:
        logging.exception("Ошибка генерации")
        await bot.send_message(chat_id, "😕 Что-то пошло не так при генерации. Попробуй ещё раз.")

# ===== ОБРАБОТЧИКИ КОМАНД =====
@dp.message(CommandStart())
async def handle_start(message: Message):
    _add_history(message.from_user.id, "start", "Запустил бота")
    await message.answer(
        "👋 <b>Привет! Я — бот-наставник по мобильной фотографии.</b>\n\n"
        "📸 <b>Бесплатный анализ:</b> пришли фото — я найду ошибки композиции и покажу их прямо на снимке.\n\n"
        "✨ <b>Улучшение фото:</b> ИИ исправит композицию, свет, уберёт лишнее и дорисует края.\n\n"
        "🎓 <b>Мини-курс по композиции (9 дней):</b> с проверкой каждого задания. Первый день — бесплатно, чтобы попробовать.\n\n"
        "💛 <b>Поддержать проект:</b> если бот оказался полезным — можно поддержать разработку.\n\n"
        "Присылай фото и начнём разбор! 👇",
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

@dp.message(Command("course"))
async def handle_course(message: Message):
    await handle_course_status_logic(message.from_user.id, message.chat.id)

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

@dp.message(Command("test"))
async def handle_test(message: Message):
    global test_mode
    if message.from_user.id != 456504792:
        await message.answer("Только автор может переключать режим.")
        return
    test_mode = not test_mode
    if test_mode:
        await message.answer("🧪 <b>Тестовый режим ВКЛ</b>\nТы видишь бота как обычный пользователь.", parse_mode="HTML")
    else:
        await message.answer("👑 <b>Режим автора ВКЛ</b>\nБесплатные генерации без ограничений.", parse_mode="HTML")

# ===== АДМИН-ПАНЕЛЬ =====
@dp.message(Command("admin"))
async def handle_admin(message: Message):
    if message.from_user.id != 456504792:
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return

    args = message.text.split()
    if len(args) == 1:
        await message.answer(
            "📊 <b>Админ-панель</b>\n\n"
            "/admin stats — общая статистика\n"
            "/admin users — список пользователей\n"
            "/admin history — последние действия\n"
            "/admin gen — генерации\n"
            "/admin course — курс",
            parse_mode="HTML"
        )
        return

    command = args[1].lower()

    if command == "stats":
        users = _load_users()
        history = _load_history()
        total_users = len(users)
        total_photos = sum(data.get("total", 0) for data in users.values())
        total_actions = sum(len(entries) for entries in history.values())
        await message.answer(
            f"📊 <b>Общая статистика</b>\n\n"
            f"👤 Пользователей: {total_users}\n"
            f"📸 Всего анализов: {total_photos}\n"
            f"📝 Всего действий: {total_actions}",
            parse_mode="HTML"
        )

    elif command == "users":
        users = _load_users()
        text = "👤 <b>Пользователи</b>\n\n"
        for uid, data in users.items():
            username = data.get("username", uid)
            total = data.get("total", 0)
            trial = "🆓" if data.get("trial", False) else "💳"
            text += f"• {trial} {username} — {total} фото\n"
        await message.answer(text, parse_mode="HTML")

    elif command == "history":
        history = _load_history()
        text = "📝 <b>Последние действия</b>\n\n"
        count = 0
        for uid, entries in reversed(history.items()):
            for entry in reversed(entries[-3:]):
                text += f"• {uid}: {entry['time']} — {entry['action']} {entry['details']}\n"
                count += 1
                if count >= 30:
                    text += "\n... (показаны последние 30 записей)"
                    await message.answer(text, parse_mode="HTML")
                    return
        await message.answer(text, parse_mode="HTML")

    elif command == "gen":
        text = "💎 <b>Генерации пользователей</b>\n\n"
        for uid, count in paid_generations.items():
            if count > 0:
                text += f"• ID {uid}: {count} шт\n"
        if text == "💎 <b>Генерации пользователей</b>\n\n":
            text += "Нет оплаченных генераций."
        await message.answer(text, parse_mode="HTML")

    elif command == "course":
        users = _load_users()
        text = "🎓 <b>Курс пользователей</b>\n\n"
        for uid, data in users.items():
            day = data.get("day", 0)
            if day > 0:
                username = data.get("username", uid)
                trial = "🆓" if data.get("trial", False) else "💳"
                text += f"• {trial} {username}: день {day}/9\n"
        if text == "🎓 <b>Курс пользователей</b>\n\n":
            text += "Никто не начал курс."
        await message.answer(text, parse_mode="HTML")

    else:
        await message.answer("❌ Неизвестная команда. Используй /admin stats, users, history, gen, course")

# ===== ЛОГИКА КУРСА =====
def _is_trial(user_id: int) -> bool:
    """Проверяет, находится ли пользователь на пробном периоде."""
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        for key, data in users.items():
            if isinstance(data, dict) and data.get("username") == str(user_id):
                uid = key
                break
        else:
            return False
    return users[uid].get("trial", False)


def _payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой оплаты курса."""
    link = create_payment_link(490, "Оплата за мини-курс по композиции")
    if not link:
        link = "https://t.me/moy_razbor_bot"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить курс (490 ₽)", url=link)],
        ]
    )


async def handle_course_status_logic(user_id: int, chat_id: int):
    """Общая логика для кнопки и команды /course."""
    if has_access(user_id):
        user_mode[user_id] = "course"
        status = get_status(user_id)
        if status is not None:
            if "День 0" in status or "Подготовка" in status:
                await bot.send_message(
                    chat_id,
                    status,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🚀 Начать курс", callback_data="start_course_btn")],
                        ]
                    ),
                )
                await send_photos(chat_id, 0)

            elif "День 1" in status and _is_trial(user_id):
                await bot.send_message(
                    chat_id,
                    status + "\n\n🆓 <b>Это твой бесплатный пробный день!</b>\n"
                    "День 0 и День 1 — бесплатно, чтобы ты мог попробовать формат обучения.\n"
                    "После выполнения задания откроется возможность оплатить полный доступ.",
                    parse_mode="HTML",
                )
                await send_photos(chat_id, 1)

            else:
                await bot.send_message(chat_id, status, parse_mode="HTML")
                users = _load_users()
                uid = str(user_id)
                if uid in users:
                    day = users[uid].get("day", 1)
                    await send_photos(chat_id, day)
        return

    # Нет доступа — показываем описание и предлагаем бесплатный старт
    await bot.send_message(
        chat_id,
        "🎓 <b>Мини-курс по композиции (9 дней)</b>\n\n"
        "9-дневный челлендж с проверкой каждого задания:\n"
        "• День 0: Подготовка телефона\n"
        "• День 1: Горизонт и геометрия 🆓\n"
        "• День 2: Правило третей\n"
        "• День 3: Поза человека\n"
        "• День 4: Свет и тени\n"
        "• День 5: Тень как приём\n"
        "• День 6: Отражения\n"
        "• День 7: Фрейминг\n"
        "• День 8: Ритм и перспектива\n"
        "• День 9: Глубина кадра\n\n"
        "🆓 <b>День 0 и День 1 — бесплатно!</b>\n"
        "Попробуй, посмотри примеры фотографий, выполни первое задание.\n\n"
        "💰 Полный доступ ко всем 9 дням: 490 ₽\n\n"
        "Начни бесплатно прямо сейчас!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🆓 Начать бесплатно", callback_data="start_trial")],
                [InlineKeyboardButton(text="💳 Оплатить полный доступ (490 ₽)", callback_data="pay_course")],
            ]
        ),
    )


# ===== КНОПКИ КУРСА =====
@dp.callback_query(F.data == "start_trial")
async def handle_start_trial(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    activate_free_trial(user_id)
    user_mode[user_id] = "course"
    status = get_status(user_id)
    if status:
        await callback.message.answer(status, parse_mode="HTML")
        await send_photos(callback.message.chat.id, 0)


@dp.callback_query(F.data == "pay_course")
async def handle_pay_course(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(490, "Оплата за мини-курс по композиции")
    if not link:
        link = "https://t.me/moy_razbor_bot"
    await callback.message.answer(
        "💳 <b>Оплата мини-курса по композиции</b>\n\n"
        "Полный доступ ко всем 9 дням: 490 ₽\n\n"
        "Нажми кнопку ниже, чтобы оплатить. После оплаты доступ откроется автоматически.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить 490 ₽", url=link)],
            ]
        ),
    )


@dp.callback_query(F.data == "course_status")
async def handle_course_status(callback: CallbackQuery):
    await callback.answer()
    await handle_course_status_logic(callback.from_user.id, callback.message.chat.id)


@dp.callback_query(F.data == "start_course_btn")
async def handle_start_course_btn(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_mode[user_id] = "course"
    add_text = add_photo(callback.from_user.id)
    if add_text:
        # Если пользователь на пробном периоде и переходит на День 1 — добавляем предупреждение
        if _is_trial(user_id) and "День 1" in add_text:
            add_text += (
                "\n\n🆓 <b>Это твой бесплатный пробный день!</b>\n"
                "День 0 и День 1 — бесплатно, чтобы ты мог попробовать формат обучения.\n"
                "После выполнения задания откроется возможность оплатить полный доступ."
            )
        await callback.message.answer(add_text, parse_mode="HTML")
        from course import get_next_day
        day = get_next_day(user_id)
        if day == 1:
            await send_photos(callback.message.chat.id, 1)
    await callback.answer()


@dp.callback_query(F.data == "mode_course")
async def handle_mode_course(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "course"
    await callback.answer("✅ Режим курса. Присылай фото для задания.")
    status = get_status(callback.from_user.id)
    if status:
        await callback.message.answer(status, parse_mode="HTML")


@dp.callback_query(F.data == "mode_free")
async def handle_mode_free(callback: CallbackQuery):
    user_mode[callback.from_user.id] = "free"
    await callback.answer("🔍 Обычный анализ. Фото не засчитается в курс.")


# ===== КНОПКИ (поддержка, покупки) =====
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

@dp.callback_query(F.data == "new_photo")
async def handle_retry_button(callback: CallbackQuery):
    await callback.message.answer("Присылай следующее фото — жду! 📷")
    await callback.answer()

# ===== МЕНЮ ПОДДЕРЖКИ =====
@dp.callback_query(F.data == "donate_menu")
async def handle_donate_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💛 <b>Поддержать проект</b>\n\n"
        "Выбери сумму. Любая поддержка помогает боту развиваться! 🙏",
        parse_mode="HTML",
        reply_markup=donate_keyboard(),
    )

async def _handle_donate(callback: CallbackQuery, amount: int):
    await callback.answer()
    link = create_payment_link(amount, f"Поддержка проекта ({amount} ₽)")
    if not link:
        await callback.message.answer(
            "⚠️ Не удалось создать платёжную ссылку. Попробуй позже.",
            parse_mode="HTML",
        )
        return
    await callback.message.answer(
        f"💛 <b>Поддержать проект на {amount} ₽</b>\n\n"
        "Спасибо, что помогаешь боту развиваться! 🙏\n\n"
        "Нажми кнопку ниже, чтобы оплатить.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=link)],
            ]
        ),
    )

@dp.callback_query(F.data == "donate_100")
async def handle_donate_100(callback: CallbackQuery):
    await _handle_donate(callback, 100)

@dp.callback_query(F.data == "donate_300")
async def handle_donate_300(callback: CallbackQuery):
    await _handle_donate(callback, 300)

@dp.callback_query(F.data == "donate_500")
async def handle_donate_500(callback: CallbackQuery):
    await _handle_donate(callback, 500)

@dp.callback_query(F.data == "buy_5_gen")
async def handle_buy_5_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(99, "Пакет 5 генераций")
    if not link:
        await callback.message.answer(
            "⚠️ Не удалось создать платёжную ссылку. Попробуй позже.",
            parse_mode="HTML",
        )
        return
    await callback.message.answer(
        "✨ <b>Пакет 5 генераций — 99 ₽</b>\n\n"
        "Нажми кнопку ниже, чтобы оплатить. После оплаты генерации зачислятся автоматически.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить 99 ₽", url=link)],
            ]
        ),
    )

@dp.callback_query(F.data == "buy_20_gen")
async def handle_buy_20_gen(callback: CallbackQuery):
    await callback.answer()
    link = create_payment_link(249, "Пакет 20 генераций")
    if not link:
        await callback.message.answer(
            "⚠️ Не удалось создать платёжную ссылку. Попробуй позже.",
            parse_mode="HTML",
        )
        return
    await callback.message.answer(
        "✨ <b>Пакет 20 генераций — 249 ₽</b>\n\n"
        "Нажми кнопку ниже, чтобы оплатить. После оплаты генерации зачислятся автоматически.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить 249 ₽", url=link)],
            ]
        ),
    )

# ===== ГЕНЕРАЦИЯ С ФОРМАТАМИ =====

def register_format_handlers():
    for fmt, name in FORMATS:

        def make_free_handler(fmt=fmt, name=name):
            @dp.callback_query(F.data == f"gen_{fmt}_free")
            async def handler(callback: CallbackQuery):
                user_id = callback.from_user.id
                gen_format[user_id] = fmt
                await callback.answer(f"Выбран: {name}")
                await callback.message.answer(
                    f"✨ Выбран формат: <b>{name}</b>\n\n"
                    "Напиши пожелание (например: «дорисуй руку, сделай свет теплее»)\n"
                    "Или напиши «ок» для стандартного улучшения.",
                    parse_mode="HTML",
                )
                user_mode[user_id] = "gen_wish_free"
            return handler

        def make_paid_handler(fmt=fmt, name=name):
            @dp.callback_query(F.data == f"gen_{fmt}_paid")
            async def handler(callback: CallbackQuery):
                user_id = callback.from_user.id
                gen_format[user_id] = fmt
                await callback.answer(f"Выбран: {name}")
                await callback.message.answer(
                    f"✨ Выбран формат: <b>{name}</b>\n\n"
                    "Напиши пожелание (например: «дорисуй руку, сделай свет теплее»)\n"
                    "Или напиши «ок» для стандартного улучшения.",
                    parse_mode="HTML",
                )
                user_mode[user_id] = "gen_wish_paid"
            return handler

        make_free_handler()
        make_paid_handler()


register_format_handlers()


@dp.callback_query(F.data == "gen_free")
async def handle_gen_free(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != 456504792 and free_generations.get(user_id, 0) >= 1:
        await callback.answer("Ты уже использовал бесплатную генерацию. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото для анализа!")
        return
    await callback.answer()
    await callback.message.answer(
        "✨ <b>Улучшение фото (бесплатно)</b>\n\n"
        "Выбери формат, затем напиши пожелание (или «ок»):",
        parse_mode="HTML",
        reply_markup=format_keyboard("free"),
    )


@dp.callback_query(F.data == "gen_paid")
async def handle_gen_paid(callback: CallbackQuery):
    user_id = callback.from_user.id
    if paid_generations.get(user_id, 0) <= 0:
        await callback.answer("У тебя нет оплаченных генераций. Купи пакет!")
        return
    if user_id not in last_photo:
        await callback.answer("Сначала пришли фото для анализа!")
        return
    await callback.answer()
    await callback.message.answer(
        "✨ <b>Улучшение фото</b>\n\n"
        f"Осталось генераций: {paid_generations.get(user_id, 0)}\n\n"
        "Выбери формат, затем напиши пожелание (или «ок»):",
        parse_mode="HTML",
        reply_markup=format_keyboard("paid"),
    )

# ===== ОБРАБОТЧИКИ СООБЩЕНИЙ =====
@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "")

    if mode in ("gen_wish_free", "gen_wish_paid"):
        gen_type = "free" if "free" in mode else "paid"
        await do_generation(user_id, message.chat.id, gen_type)
        user_mode[user_id] = "free"
        return

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
            _add_history(user_id, "analysis", f"Ошибки: {error_type}")

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
            f"❌ Что не так: {result.get('what_is_wrong', '---')}\n\n"
            f"🔄 Как исправить: {result.get('how_to_fix', '---')}\n\n"
            f"✨ Совет от профи: {result.get('pro_tip', '---')}\n\n"
            f"👍 Что хорошо: {result.get('praise', '---')}\n\n"
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
                    if _is_trial(user_id) and "задание выполнено" in check_text.lower():
                        link = create_payment_link(490, "Оплата за мини-курс по композиции")
                        if not link:
                            link = "https://t.me/moy_razbor_bot"
                        check_text += (
                            "\n\n🎉 <b>Поздравляю! Ты прошёл бесплатный пробный день!</b>\n\n"
                            "Теперь ты знаешь, как проходит обучение.\n\n"
                            "📚 <b>Что дальше:</b>\n"
                            "• День 2: Правило третей\n"
                            "• День 3: Поза человека\n"
                            "• День 4: Свет и тени\n"
                            "• День 5: Тень как приём\n"
                            "• День 6: Отражения\n"
                            "• День 7: Фрейминг\n"
                            "• День 8: Ритм и перспектива\n"
                            "• День 9: Глубина кадра\n\n"
                            "💳 <b>Оплати полный доступ за 490 ₽ и продолжай учиться!</b>"
                        )
                        await message.answer(
                            check_text,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [InlineKeyboardButton(text="💳 Оплатить курс (490 ₽)", url=link)],
                                ]
                            ),
                        )
                    else:
                        await message.answer(check_text, parse_mode="HTML")

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
        user_mode[user_id] = "free"
        return

    await message.answer(
        "Пришли мне, пожалуйста, фотографию 📷 — я умею разбирать только изображения."
    )

# ===== ЗАПУСК =====
async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
