"""
Мини-курс по композиции: 8-дневный челлендж (День 0 + 7 дней) с проверкой заданий
"""
import json
import os

COURSE_FILE = "course_users.json"

DAYS = {
    0: {
        "title": "Подготовка к курсу",
        "theory": (
            "Перед тем как начать — настрой телефон. Это займёт 2 минуты, но сэкономит часы.\n\n"
            "📱 <b>1. Протри объектив</b>\n"
            "Грязный объектив — мутный кадр, засветы, ореолы. Протирай мягкой тканью перед каждой съёмкой.\n\n"
            "📐 <b>2. Включи сетку и уровень</b>\n"
            "Сетка: Настройки → Камера → Сетка (вкл). Показывает правило третей и помогает ровнять горизонт.\n"
            "Уровень: на многих телефонах есть встроенный уровень (линия по центру). Когда телефон ровно — линия сплошная.\n\n"
            "🔍 <b>3. Зум: оптический и цифровой</b>\n"
            "Оптический зум (кнопки 1x, 2x, 3x, 5x) — используй смело, качество не теряется.\n"
            "Цифровой зум (щипок пальцами) — не используй. Это просто растянутая картинка.\n"
            "Нужно ближе — подойди ногами или переключи оптический зум.\n\n"
            "🖼️ <b>4. Форматы кадра</b>\n"
            "4:3 — стандарт, максимум информации. Используй на курсе.\n"
            "1:1 (квадрат) — для симметрии и Instagram.\n"
            "16:9 — для пейзажей и панорам.\n"
            "9:16 — вертикальное видео.\n\n"
            "🌓 <b>5. HDR: что это и когда включать</b>\n"
            "HDR — телефон делает несколько снимков с разной яркостью и склеивает. Помогает при ярком небе и тёмных тенях.\n"
            "Когда включать: пейзажи, контровой свет, помещение против окна.\n"
            "Когда выключить: движение в кадре (HDR делает смаз).\n"
            "На большинстве телефонов HDR авто — можно оставить.\n\n"
            "🌙 <b>6. Ночной режим и макро</b>\n"
            "Работают по-разному на разных телефонах. Обычно включаются автоматически. Если нет — в меню «Режимы» или «Ещё».\n"
            "Ночной режим: значок луны 🌙. Держи телефон неподвижно 2-3 секунды.\n"
            "Макро: значок цветка 🌸. При близкой съёмке. Дай сфокусироваться.\n\n"
            "✨ <b>7. Экспозиция: ярче или темнее</b>\n"
            "Тапни по экрану — появится квадрат фокуса и солнышко ☀️.\n"
            "Тяни солнышко вверх (светлее) или вниз (темнее).\n"
            "Когда затемнять: небо «выбито» в белый — затемни, чтобы вернуть облака.\n"
            "Когда осветлять: объект в тени — осветли, чтобы показать детали.\n"
            "Это творческий инструмент: затемнение = драма, осветление = воздушность.\n\n"
            "💡 <b>Главное правило</b>\n"
            "Телефон сам выставляет экспозицию и фокус. Твоя задача — композиция. Об этом весь курс."
        ),
        "task": "Напиши «Начать курс», чтобы перейти к Дню 1.",
        "check": "",
        "error_type": "",
        "is_intro": True,
    },
    1: {
        "title": "Горизонт и геометрия",
        "theory": (
            "Горизонт — первое, что замечает зритель. Заваленный горизонт создаёт ощущение беспорядка. Всегда проверяй вертикальные и горизонтальные линии: столбы, углы зданий, линия водоёма.\n\n"
            "⚠️ Если снимаешь архитектуру на широкий угол (1x) — вертикали могут «заваливаться». Отойди подальше и включи оптический зум 2x или 3x — перспектива станет ровнее."
        ),
        "task": "Сфоткай пейзаж, архитектуру или интерьер так, чтобы горизонт был идеально ровным, а вертикальные линии — строго вертикальны.",
        "check": "Главное: горизонт ровный, вертикали не завалены.",
        "error_type": "horizon",
    },
    2: {
        "title": "Правило третей",
        "theory": (
            "Раздели кадр на 9 равных частей. Главный объект размещай на пересечении линий или вдоль них — это делает кадр динамичнее. Не бойся оставлять «воздух» — пустое пространство по направлению взгляда."
        ),
        "task": "Сними портрет, натюрморт или животное, разместив объект на правой или левой трети кадра. Оставь свободное пространство перед объектом.",
        "check": "Главное: объект смещён к одной из третей, есть воздух по направлению взгляда.",
        "error_type": "thirds",
    },
    3: {
        "title": "Поза человека",
        "theory": (
            "Анфас с коленями и плечами прямо в камеру делает фигуру плоской. Разворот корпуса на 30–45° создаёт объём. Плечи и таз должны быть на разных линиях — это создаёт диагональ и элегантность. Следи за подбородком: прижатый к шее добавляет тяжести, слегка приподнятый — вытягивает силуэт.\n\n"
            "⚠️ Не снимай человека на широкий угол (1x) с близкого расстояния — лицо исказится, нос станет больше. Отойди на пару шагов и включи зум 2x — пропорции будут естественными."
        ),
        "task": "Сфоткай человека в полуобороте. Плечи расправлены, подбородок не прижат, таз и плечи на разных линиях. Точка съёмки — на уровне глаз или чуть ниже.",
        "check": "Главное: модель не стоит строго анфас, есть разворот, плечи и таз не на одной линии.",
        "error_type": "pose",
    },
    4: {
        "title": "Свет и тени",
        "theory": (
            "Свет создаёт объём и настроение. Боковой свет подчёркивает фактуру, контровой — создаёт силуэт. Избегай плоского фронтального света (вспышка в лоб) и случайных теней от фотографа."
        ),
        "task": "Сними объект при боковом свете — от окна днём или на улице утром/вечером. Тень должна подчёркивать форму, а не отвлекать.",
        "check": "Главное: свет падает сбоку, тень работает на объём.",
        "error_type": "lighting",
    },
    5: {
        "title": "Тень как приём",
        "theory": (
            "Тень может быть главным героем кадра. Длинные тени на закате, графичные тени от жалюзи, силуэты добавляют графику, загадку и глубину."
        ),
        "task": "Поймай интересную тень — от дерева, окна, лестницы, человека. Тень должна быть осознанной частью композиции.",
        "check": "Главное: тень — ключевой элемент кадра, а не случайный артефакт.",
        "error_type": "shadow",
    },
    6: {
        "title": "Отражения",
        "theory": (
            "Лужи, зеркала, витрины, стёкла, водная гладь. Отражение удваивает мир и добавляет сюрреализма. Съёмка через отражение создаёт многослойность."
        ),
        "task": "Найди отражение — в луже, окне, зеркале, воде. Сними так, чтобы отражение взаимодействовало с реальностью.",
        "check": "Главное: отражение — осознанная часть композиции.",
        "error_type": "reflection",
    },
    7: {
        "title": "Фрейминг, ритм и слои",
        "theory": (
            "Естественная рамка (арка, ветки, дверной проём) привлекает внимание к объекту. Повторяющиеся элементы (ступени, колонны, окна) создают ритм. Передний/средний/задний план дают глубину."
        ),
        "task": "Сними кадр, где есть хотя бы два из трёх: рамка (арка, окно), ритм (повторяющиеся элементы), слои (передний/задний план).",
        "check": "Главное: в кадре есть рамка ИЛИ ритм ИЛИ слои — минимум два приёма из трёх.",
        "error_type": "framing",
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


def has_access(user_id: int) -> bool:
    if user_id == 456504792:
        return True
    users = _load_users()
    return str(user_id) in users


def activate_by_username(username: str):
    users = _load_users()
    if username in users:
        return
    users[username] = {
        "day": 0,
        "completed": [],
        "photos_today": [],
        "attempts": 0,
        "username": username,
    }
    _save_users(users)


def get_status(user_id: int) -> str | None:
    if not has_access(user_id):
        return None
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        found = False
        for key, data in users.items():
            if isinstance(data, dict) and data.get("username") == uid:
                found = True
                uid = key
                break
        if not found and user_id == 456504792:
            users["456504792"] = {"day": 0, "completed": [], "photos_today": [], "attempts": 0, "username": "sevosphoto"}
            _save_users(users)
            return _day_text(0)
        elif not found:
            return None

    day = users[uid].get("day", 1)
    photos_today = users[uid].get("photos_today", [])
    if day == 0:
        return _day_text(0)
    if day > 7:
        return _course_result(uid)
    if len(photos_today) < 3:
        return _day_text(day) + f"\n\n📸 Отправь ещё {3 - len(photos_today)} фото по заданию."
    return _day_text(day)


def add_photo(user_id: int) -> str:
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
            if user_id == 456504792:
                users["456504792"] = {"day": 0, "completed": [], "photos_today": [], "attempts": 0, "username": "sevosphoto"}
                _save_users(users)
                return ""
            return ""

    day = users[uid]["day"]
    if day == 0:
        users[uid]["day"] = 1
        users[uid]["photos_today"] = []
        users[uid]["attempts"] = 0
        _save_users(users)
        return "🚀 Поехали!\n\n" + _day_text(1)
    if day > 7:
        return ""

    users[uid]["photos_today"] = users[uid].get("photos_today", []) + [1]
    count = len(users[uid]["photos_today"])
    _save_users(users)

    if count == 1:
        return "✅ Первое фото принято! Пришли ещё 2."
    elif count == 2:
        return "✅ Второе фото принято! Пришли ещё 1."
    elif count >= 3:
        users[uid]["attempts"] = users[uid].get("attempts", 0) + 1
        _save_users(users)
        return "THIRD_PHOTO"
    return ""


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


def get_current_topic(user_id: int) -> str | None:
    if not has_access(user_id):
        return None
    users = _load_users()
    uid = str(user_id)
    if uid not in users:
        for key, data in users.items():
            if isinstance(data, dict) and data.get("username") == uid:
                uid = key
                break
        else:
            return None
    day = users[uid]["day"]
    if day == 0 or day > 7:
        return None
    return DAYS[day]["title"]


def _day_text(day: int) -> str:
    d = DAYS[day]
    if day == 0:
        return (
            f"📚 <b>День 0: {d['title']}</b>\n\n"
            f"{d['theory']}\n\n"
            f"{d['task']}"
        )
    return (
        f"📚 <b>День {day}: {d['title']}</b>\n\n"
        f"<b>Теория:</b>\n{d['theory']}\n\n"
        f"<b>Задание:</b> {d['task']}\n\n"
        f"📸 Пришли <b>3 фотографии</b> по заданию."
    )


def _course_result(uid: str) -> str:
    users = _load_users()
    completed = users[uid].get("completed", [])
    return (
        "🎉 <b>Ты прошёл весь мини-курс!</b>\n\n"
        f"Пройдено дней: {len(completed)} из 7\n\n"
        "Ты освоил: горизонт, правило третей, позу, свет, тень, отражения, фрейминг.\n\n"
        "Теперь снимай как профи! 🚀"
    )
