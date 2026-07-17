"""
Хранение и отображение статистики пользователей
"""
import json
import os

STATS_FILE = "stats.json"

def _load_stats() -> dict:
    if not os.path.exists(STATS_FILE):
        return {}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_stats(stats: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def add_analysis(user_id: int, error_type: str):
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {"total": 0, "errors": {}}
    stats[uid]["total"] += 1

    errors = [e.strip() for e in error_type.split(",")]
    for err in errors:
        if err and err != "good_shot":
            stats[uid]["errors"][err] = stats[uid]["errors"].get(err, 0) + 1

    _save_stats(stats)

def get_stats(user_id: int) -> str:
    stats = _load_stats()
    uid = str(user_id)
    if uid not in stats or stats[uid]["total"] == 0:
        return "У тебя пока нет статистики. Пришли фото на анализ!"

    data = stats[uid]
    total = data["total"]
    errors = data["errors"]

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
        "good_shot": "Отличный кадр",
    }

    text = f"📊 <b>Твоя статистика</b>\nПроанализировано фото: <b>{total}</b>\n\n"
    if errors:
        text += "Частые ошибки:\n"
        for err, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            name = error_names.get(err, err)
            text += f"  • {name}: {count} раз(а)\n"

        top_error = max(errors, key=errors.get)
        top_name = error_names.get(top_error, top_error)
        text += f"\n💡 Совет: поработай над <b>{top_name.lower()}</b> — это твоя главная зона роста!"
    else:
        text += "Ошибок нет — ты снимаешь как профи! 🎉"

    return text
