"""
Хранение и отображение статистики пользователей + история действий
"""
import json
import os
from datetime import datetime

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
        stats[uid] = {"total": 0, "errors": {}}

    # Защита от старых записей без "errors"
    if "errors" not in stats[uid] or not isinstance(stats[uid]["errors"], dict):
        stats[uid]["errors"] = {}

    stats[uid]["total"] = stats[uid].get("total", 0) + 1

    errors = [e.strip() for e in error_type.split(",")]
    for err in errors:
        if err and err != "good_shot":
            stats[uid]["errors"][err] = stats[uid]["errors"].get(err, 0) + 1

    _save_stats(stats)

    # Добавляем в историю
    add_history(user_id, "analysis", f"Анализ фото: {error_type}")


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
    # Оставляем только последние 100 записей на пользователя
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

    error_names = {
        "horizon": "Горизонт",
        "thirds": "Правило третей",
        "leading_lines": "Ведущие линии",
        "framing": "Фрейминг",
        "balance": "Равновесие",
        "shadow": "Тень",
        "fill_frame": "Заполнение кадра",
        "distortion": "Искажения",
        "pose": "Поза",
        "lighting": "Освещение",
        "rhythm": "Ритм",
        "silhouette": "Силуэт",
        "reflection": "Отражения",
        "cropping": "Кадрирование",
        "perspective": "Перспектива",
        "color": "Цвет",
        "sharpness": "Резкость",
        "emotion": "Эмоция",
        "depth": "Глубина кадра",
        "symmetry": "Симметрия",
        "diagonal": "Диагональ",
        "topic_error": "Ошибка в задании",
    }

    text = f"📊 <b>Твоя статистика</b>\nПроанализировано фото: <b>{total}</b>\n\n"
    if errors:
        text += "Частые ошибки:\n"
        for err, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            name = error_names.get(err, err)
            text += f" • {name}: {count} раз(а)\n"

        real_errors = {k: v for k, v in errors.items() if k not in ("good_shot", "topic_error")}
        if real_errors:
            top_error = max(real_errors, key=real_errors.get)
            top_name = error_names.get(top_error, top_error)
            text += f"\n💡 Совет: поработай над <b>{top_name.lower()}</b> — это твоя главная зона роста!"
        else:
            text += "\n🎉 У тебя нет типичных ошибок — ты снимаешь как профи!"
    else:
        text += "🎉 Ошибок нет — ты снимаешь как профи!"

    return text


def get_admin_stats() -> str:
    """Возвращает общую статистику для админа"""
    stats = _load_stats()
    history = _load_history()

    total_users = len(stats)
    total_photos = sum(data.get("total", 0) for data in stats.values())
    total_history = sum(len(entries) for entries in history.values())

    return (
        f"📊 <b>Общая статистика</b>\n\n"
        f"👤 Пользователей: {total_users}\n"
        f"📸 Всего анализов: {total_photos}\n"
        f"📝 Всего действий: {total_history}"
    )


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
