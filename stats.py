"""
Хранение и отображение статистики пользователей + история действий
"""
import json
import os
from datetime import datetime, timedelta

from firebase_db import fb_get, fb_set

STATS_FILE = "stats.json"
HISTORY_FILE = "history.json"


def _load_stats() -> dict:
    return fb_get("stats", default={}) or {}


def _save_stats(stats: dict):
    fb_set("stats", stats)


def _load_history() -> dict:
    return fb_get("history", default={}) or {}


def _save_history(history: dict):
    fb_set("history", history)


def add_analysis(user_id: int, error_type: str):
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {"total": 0, "errors": {}, "today": {}, "tools": {}}

    if "errors" not in stats[uid] or not isinstance(stats[uid]["errors"], dict):
        stats[uid]["errors"] = {}
    if "today" not in stats[uid] or not isinstance(stats[uid]["today"], dict):
        stats[uid]["today"] = {}
    if "tools" not in stats[uid] or not isinstance(stats[uid]["tools"], dict):
        stats[uid]["tools"] = {}

    stats[uid]["total"] = stats[uid].get("total", 0) + 1

    day = datetime.now().strftime("%Y-%m-%d")
    stats[uid]["today"][day] = stats[uid]["today"].get(day, 0) + 1
    if len(stats[uid]["today"]) > 60:
        sorted_days = sorted(stats[uid]["today"].keys())
        for old in sorted_days[:-60]:
            del stats[uid]["today"][old]

    errors = [e.strip() for e in error_type.split(",")]
    for err in errors:
        if err and err != "good_shot":
            stats[uid]["errors"][err] = stats[uid]["errors"].get(err, 0) + 1

    _save_stats(stats)
    add_history(user_id, "analysis", f"Анализ фото: {error_type}")


def add_tool_use(user_id: int, tool: str):
    """Записывает использование инструмента (улучшение, стилизация, flat_lay и т.д.)"""
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {"total": 0, "errors": {}, "today": {}, "tools": {}}
    if "tools" not in stats[uid] or not isinstance(stats[uid]["tools"], dict):
        stats[uid]["tools"] = {}
    if "today" not in stats[uid] or not isinstance(stats[uid]["today"], dict):
        stats[uid]["today"] = {}

    stats[uid]["tools"][tool] = stats[uid]["tools"].get(tool, 0) + 1

    day = datetime.now().strftime("%Y-%m-%d")
    stats[uid]["today"][day] = stats[uid]["today"].get(day, 0) + 1

    _save_stats(stats)
    add_history(user_id, "tool", f"Использован: {tool}")


def add_history(user_id: int, action: str, details: str = ""):
    """Записывает действие пользователя в историю"""
    history = _load_history()
    uid = str(user_id)
    if uid not in history:
        history[uid] = []
    history[uid].append({
        "time": datetime.now().isoformat(),
        "action": action,
        "details": details
    })
    if len(history[uid]) > 100:
        history[uid] = history[uid][-100:]
    _save_history(history)


def get_history(user_id: int, limit: int = 20) -> list:
    """Возвращает последние действия пользователя"""
    history = _load_history()
    uid = str(user_id)
    if uid not in history:
        return []
    return history[uid][-limit:]


def get_stats(user_id: int) -> str:
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats or stats[uid].get("total", 0) == 0:
        return "У тебя пока нет статистики. Пришли фото на анализ!"

    data = stats[uid]
    total = data.get("total", 0)
    errors = data.get("errors", {})
    today_map = data.get("today", {})
    tools = data.get("tools", {})

    error_names = {
        "horizon": "Горизонт", "thirds": "Правило третей",
        "leading_lines": "Ведущие линии", "framing": "Фрейминг",
        "balance": "Равновесие", "shadow": "Тень",
        "fill_frame": "Заполнение кадра", "distortion": "Искажения",
        "pose": "Поза", "lighting": "Освещение",
        "rhythm": "Ритм", "silhouette": "Силуэт",
        "reflection": "Отражения", "cropping": "Кадрирование",
        "perspective": "Перспектива", "color": "Цвет",
        "sharpness": "Резкость", "emotion": "Эмоция",
        "depth": "Глубина кадра", "symmetry": "Симметрия",
        "diagonal": "Диагональ", "topic_error": "Ошибка в задании",
    }
    tool_names = {
        "improve": "✨ Улучшение", "style": "🎨 Стилизация",
        "flat_lay": "📷 Flat Lay", "doc": "📄 Документы",
        "studio": "🧑💼 Студийный портрет", "ref": "🖼️ По референсу",
        "prompt": "🎨 Создание изображения", "change": "✂️ Редактор",
        "xmas": "🎄 Новогодняя", "holiday": "🎉 Праздники",
        "wedding": "💒 Свадьба", "daily": "🔮 Карта дня",
    }

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    today_count = today_map.get(today, 0)
    week_count = sum(c for d, c in today_map.items() if d >= week_ago)
    month_count = sum(c for d, c in today_map.items() if d >= month_ago)

    text = f"📊 <b>Твоя статистика</b>\n\n"
    text += f"📸 Всего действий: <b>{total}</b>\n"
    text += f"📅 Сегодня: <b>{today_count}</b>\n"
    text += f"📅 За 7 дней: <b>{week_count}</b>\n"
    text += f"📅 За 30 дней: <b>{month_count}</b>\n"

    if tools:
        text += "\n🛠 <b>Что использовал:</b>\n"
        for t, c in sorted(tools.items(), key=lambda x: x[1], reverse=True):
            text += f" • {tool_names.get(t, t)}: {c}\n"

    if errors:
        text += "\n❌ <b>Частые ошибки:</b>\n"
        for err, count in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:7]:
            text += f" • {error_names.get(err, err)}: {count}\n"

        real_errors = {k: v for k, v in errors.items() if k not in ("good_shot", "topic_error")}
        if real_errors:
            top_error = max(real_errors, key=real_errors.get)
            text += f"\n💡 Совет: поработай над <b>{error_names.get(top_error, top_error).lower()}</b> — это твоя главная зона роста!"
        else:
            text += "\n🎉 У тебя нет типичных ошибок — ты снимаешь как профи!"

    if len(today_map) >= 14:
        last_week = sum(c for d, c in today_map.items() if week_ago <= d <= today)
        prev_week_start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        prev_week = sum(c for d, c in today_map.items() if prev_week_start <= d < week_ago)
        if prev_week > 0:
            diff = last_week - prev_week
            if diff > 0:
                text += f"\n📈 Прогресс: +{diff} к прошлой неделе — так держать!"
            elif diff < 0:
                text += f"\n📉 Прогресс: {diff} к прошлой неделе — не сдавайся!"

    return text


def get_admin_stats() -> str:
    stats = _load_stats()
    history = _load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    total_users = len(stats)
    total_actions = sum(data.get("total", 0) for data in stats.values())

    today_actions = 0
    week_actions = 0
    active_today = set()
    active_week = set()
    all_errors = {}
    all_tools = {}

    for uid, data in stats.items():
        today_map = data.get("today", {})
        today_actions += today_map.get(today, 0)
        week_actions += sum(c for d, c in today_map.items() if d >= week_ago)
        if today_map.get(today, 0) > 0:
            active_today.add(uid)
        if any(d >= week_ago for d in today_map):
            active_week.add(uid)
        for err, c in data.get("errors", {}).items():
            all_errors[err] = all_errors.get(err, 0) + c
        for t, c in data.get("tools", {}).items():
            all_tools[t] = all_tools.get(t, 0) + c

    tool_names = {
        "improve": "✨ Улучшение", "style": "🎨 Стилизация",
        "flat_lay": "📷 Flat Lay", "doc": "📄 Документы",
        "studio": "🧑💼 Студийный портрет", "ref": "🖼️ По референсу",
        "prompt": "🎨 Создание изображения", "change": "✂️ Редактор",
    }
    error_names = {
        "horizon": "Горизонт", "thirds": "Правило третей",
        "pose": "Поза", "lighting": "Освещение",
        "shadow": "Тень", "fill_frame": "Заполнение кадра",
        "cropping": "Кадрирование", "distortion": "Искажения",
        "framing": "Фрейминг", "balance": "Равновесие",
    }

    text = f"📊 <b>Общая статистика</b>\n\n"
    text += f"👤 Всего пользователей: <b>{total_users}</b>\n"
    text += f"🟢 Активных сегодня: <b>{len(active_today)}</b>\n"
    text += f"🟢 Активных за 7 дней: <b>{len(active_week)}</b>\n\n"
    text += f"📸 Всего действий: <b>{total_actions}</b>\n"
    text += f"📅 Сегодня: <b>{today_actions}</b>\n"
    text += f"📅 За 7 дней: <b>{week_actions}</b>\n"

    if all_tools:
        text += "\n🛠 <b>Топ инструментов:</b>\n"
        for t, c in sorted(all_tools.items(), key=lambda x: x[1], reverse=True)[:7]:
            text += f" • {tool_names.get(t, t)}: {c}\n"

    if all_errors:
        text += "\n❌ <b>Топ ошибок у всех:</b>\n"
        for err, c in sorted(all_errors.items(), key=lambda x: x[1], reverse=True)[:7]:
            text += f" • {error_names.get(err, err)}: {c}\n"

    return text


def get_admin_users() -> str:
    """Возвращает список пользователей для админа"""
    stats = _load_stats()
    text = "👤 <b>Пользователи</b>\n\n"
    for uid, data in sorted(stats.items(), key=lambda x: x[1].get("total", 0), reverse=True):
        text += f"• ID: {uid}\n"
        text += f"  Анализов: {data.get('total', 0)}\n"
    return text


def get_admin_history(user_id: int = None) -> str:
    """Возвращает историю действий для админа"""
    history = _load_history()
    if user_id:
        uid = str(user_id)
        if uid not in history:
            return f"Нет истории для пользователя {user_id}"
        entries = history[uid][-20:]
        text = f"📝 <b>История пользователя {user_id}</b>\n\n"
        for entry in reversed(entries):
            text += f"• {entry['time']}: {entry['action']} {entry['details']}\n"
        return text

    text = "📝 <b>Последние действия всех пользователей</b>\n\n"
    count = 0
    for uid, entries in reversed(history.items()):
        for entry in reversed(entries[-3:]):
            text += f"• {uid}: {entry['time']} — {entry['action']} {entry['details']}\n"
            count += 1
            if count >= 30:
                return text + "\n... (показаны последние 30 записей)"
    return text
