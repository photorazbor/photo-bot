@dp.message(Command("admin"))
async def handle_admin(message: Message):
    # Только автор (ваш ID)
    if message.from_user.id != 456504792:
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return

    args = message.text.split()
    if len(args) == 1:
        await message.answer(
            "📊 <b>Админ-панель</b>\n\n"
            "Доступные команды:\n"
            "/admin stats — общая статистика\n"
            "/admin users — список пользователей\n"
            "/admin gen — генерации пользователей\n"
            "/admin course — курс пользователей",
            parse_mode="HTML"
        )
        return

    command = args[1].lower()

    if command == "stats":
        # Общая статистика
        users = _load_users()  # из course.py
        total_users = len(users)
        total_photos = 0
        for uid, data in users.items():
            total_photos += data.get("total", 0)
        await message.answer(
            f"📊 <b>Общая статистика</b>\n\n"
            f"👤 Всего пользователей: {total_users}\n"
            f"📸 Всего анализов: {total_photos}\n"
            f"🆓 Бесплатных генераций использовано: {sum(free_generations.values())}\n"
            f"💎 Оплаченных генераций осталось: {sum(paid_generations.values())}",
            parse_mode="HTML"
        )

    elif command == "users":
        # Список пользователей (первые 20)
        users = _load_users()
        text = "👤 <b>Пользователи (первые 20)</b>\n\n"
        count = 0
        for uid, data in users.items():
            if count >= 20:
                break
            username = data.get("username", uid)
            text += f"• {username} (ID: {uid})\n"
            count += 1
        await message.answer(text, parse_mode="HTML")

    elif command == "gen":
        # Генерации
        text = "💎 <b>Генерации пользователей</b>\n\n"
        for uid, count in paid_generations.items():
            if count > 0:
                text += f"• ID {uid}: {count} генераций\n"
        if text == "💎 <b>Генерации пользователей</b>\n\n":
            text += "Нет оплаченных генераций."
        await message.answer(text, parse_mode="HTML")

    elif command == "course":
        # Курс
        users = _load_users()
        text = "🎓 <b>Курс пользователей</b>\n\n"
        for uid, data in users.items():
            day = data.get("day", 0)
            if day > 0:
                username = data.get("username", uid)
                text += f"• {username}: день {day}/9\n"
        if text == "🎓 <b>Курс пользователей</b>\n\n":
            text += "Никто не начал курс."
        await message.answer(text, parse_mode="HTML")

    else:
        await message.answer("❌ Неизвестная команда. Используй /admin stats, users, gen, course")
