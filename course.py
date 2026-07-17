"""
Мини-курс по композиции: 5-дневный челлендж
"""
import json
import os
from datetime import datetime, timedelta

COURSE_FILE = "course_users.json"

DAYS = {
    1: {
        "title": "Горизонт и геометрия",
        "theory": "Горизонт — это первое, что замечает зритель. Заваленный горизонт создаёт ощущение беспорядка. Всегда проверяй вертикальные и горизонтальные линии в кадре.",
        "task": "Сфоткай пейзаж или архитектуру так, чтобы горизонт был идеально ровным, а вертикальные линии — строго вертикальны.",
    },
    2: {
        "title": "Правило третей",
        "theory": "Раздели кадр на 9 равных частей. Главный объект размещай на пересечении линий — это делает кадр динамичнее и интереснее, чем центр.",
        "task": "Сними портрет или натюрморт, разместив объект на правой или левой трети кадра. Оставь «воздух» по направлению взгляда.",
    },
    3: {
        "title": "Поза человека",
        "theory": "Анфас с коленями в камеру делает фигуру плоской. Разворот на 30-45° добавляет объём, перспективу и элегантность. Следи за плечами и тазом.",
        "task": "Сфоткай человека (можно себя) в полуобороте. Плечи и таз должны быть на разных линиях — создай диагональ.",
    },
    4: {
        "title": "Свет и тени",
        "theory": "Свет делает кадр объёмным. Боковой свет подчёркивает фактуру, контровой — создаёт силуэт. Избегай плоского фронтального света и случайных теней.",
        "task": "Сними объект при боковом свете (от окна или на улице утром/вечером). Тень должна работать на кадр, а не мешать.",
    },
    5: {
        "title": "Фрейминг и ритм",
        "theory": "Используй естественные рамки (арки, ветки, двери) чтобы привлечь внимание к объекту. Повторяющиеся элементы создают ритм и удерживают взгляд.",
        "task": "Найди естественную рамку (окно, арку, ветки) и сними через неё объект. Или покажи ритм — повторяющиеся ступени, колонны, окна.",
    },
}


def _load_users() -> dict:
    if not os.path.exists(COURSE_FILE):
        return {}
    with open(COURSE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict):
    with open(COURSE_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def start_course(user_id: int) -> str:
    users = _load_users()
    uid = str(user_id)
    now = datetime.now().isoformat()
    users[uid] = {"day": 1, "started": now, "completed": []}
    _save_users(users)
    return _day_text(1)


def get_status(user_id: int) -> str | None:
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        return None
    day = users[uid]["day"]
    if day > 5:
        return "🎉 Ты прошёл весь мини-курс! Поздравляю!\n\nТы освоил горизонт, правило третей, позу, свет и фрейминг. Теперь снимай как профи!"
    return _day_text(day)


def complete_day(user_id: int) -> str:
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        return "Ты ещё не начал курс. Нажми «Пройти мини-курс»."
    users[uid]["completed"].append(users[uid]["day"])
    users[uid]["day"] += 1
    _save_users(users)
    if users[uid]["day"] > 5:
        return "🎉 Ты прошёл весь мини-курс! Поздравляю!\n\nТы освоил горизонт, правило третей, позу, свет и фрейминг. Теперь снимай как профи!"
    return f"✅ День {users[uid]['day'] - 1} пройден!\n\n" + _day_text(users[uid]["day"])


def _day_text(day: int) -> str:
    d = DAYS[day]
    return (
        f"📚 <b>День {day}: {d['title']}</b>\n\n"
        f"<b>Теория:</b> {d['theory']}\n\n"
        f"<b>Задание:</b> {d['task']}\n\n"
        f"Пришли фото — я разберу его и мы пойдём дальше!"
    )