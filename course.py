def check_day(user_id: int, result: dict) -> str:
    if not has_access(user_id):
        return ""
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        for key, data in users.items():
            if isinstance(data, dict) and data.get("username") == uid:
                uid = key
                break
        else:
            return ""

    day = users[uid]["day"]
    if day == 0 or day > 7:
        return ""

    attempts = users[uid].get("attempts", 1)
    check_text = DAYS[day]["check"]
    error_type = result.get("error_type", "")
    what_is_wrong = result.get("what_is_wrong", "")

    # Проверяем, выполнено ли задание
    is_done = (
        error_type == "good_shot" or
        "выполнено" in what_is_wrong.lower() or
        "правильно" in what_is_wrong.lower()
    )

    if is_done:
        verdict = "done"
    elif attempts < 2:
        verdict = "retry"
    else:
        verdict = "fail"

    if verdict == "done":
        users[uid]["completed"].append(day)
        users[uid]["day"] += 1
        users[uid]["photos_today"] = []
        users[uid]["attempts"] = 0
        _save_users(users)
        if users[uid]["day"] > 7:
            return "✅ Задание выполнено!\n\n" + _course_result(uid)
        return f"✅ Задание выполнено!\n\n{check_text}\n\n" + _day_text(users[uid]["day"])

    elif verdict == "retry":
        users[uid]["photos_today"] = []
        _save_users(users)
        return f"⚠️ Почти получилось! Приём виден, но есть ошибка.\n\n{check_text}\n\nПришли ещё 3 фото — и идём дальше."

    else:
        users[uid]["photos_today"] = []
        users[uid]["attempts"] = 0
        _save_users(users)
        return f"❌ Задание не выполнено.\n\n{check_text}\n\nПришли 3 новых фото для пересдачи."
