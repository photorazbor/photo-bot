"""
Модуль для работы с Firebase Realtime Database.
Все данные бота (балансы, промокоды, заказы) хранятся в облаке.
"""
import os
import base64
import json
import logging

logger = logging.getLogger(__name__)

_db = None


def init_firebase():
    """Инициализация Firebase. Вызывается один раз при старте бота."""
    global _db
    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, db

        creds_b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64")
        if not creds_b64:
            logger.error("❌ FIREBASE_CREDENTIALS_BASE64 не задан в переменных окружения")
            return None

        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            creds_dict = json.loads(creds_json)
        except Exception as e:
            logger.exception(f"❌ Не удалось раскодировать Base64: {e}")
            return None

        project_id = creds_dict.get("project_id")
        if not project_id:
            logger.error("❌ project_id не найден в credentials")
            return None

        cred = credentials.Certificate(creds_dict)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                "databaseURL": f"https://{project_id}-default-rtdb.firebaseio.com"
            })

        _db = db
        logger.info(f"✅ Firebase подключён: {project_id}")
        return _db
    except Exception as e:
        logger.exception(f"❌ Ошибка инициализации Firebase: {e}")
        return None


def fb_get(path: str, default=None):
    """Читает данные по пути. path = 'generations/free' и т.д."""
    try:
        db = init_firebase()
        if db is None:
            return default
        ref = db.reference(path)
        data = ref.get()
        return data if data is not None else default
    except Exception as e:
        logger.exception(f"❌ fb_get({path}): {e}")
        return default


def fb_set(path: str, value):
    """Записывает данные по пути."""
    try:
        db = init_firebase()
        if db is None:
            return False
        ref = db.reference(path)
        ref.set(value)
        return True
    except Exception as e:
        logger.exception(f"❌ fb_set({path}): {e}")
        return False


def fb_update(path: str, value: dict):
    """Обновляет часть данных по пути."""
    try:
        db = init_firebase()
        if db is None:
            return False
        ref = db.reference(path)
        ref.update(value)
        return True
    except Exception as e:
        logger.exception(f"❌ fb_update({path}): {e}")
        return False


def fb_delete(path: str):
    """Удаляет данные по пути."""
    try:
        db = init_firebase()
        if db is None:
            return False
        ref = db.reference(path)
        ref.delete()
        return True
    except Exception as e:
        logger.exception(f"❌ fb_delete({path}): {e}")
        return False


def has_agreed(user_id: int) -> bool:
    """Проверяет, дал ли пользователь согласие."""
    data = fb_get("agreements", default={}) or {}
    rec = data.get(str(user_id), {})
    return rec.get("agreed", False)


def save_agreement(user_id: int, version: str = "1.0"):
    """Сохраняет факт согласия."""
    from datetime import datetime
    data = fb_get("agreements", default={}) or {}
    data[str(user_id)] = {
        "agreed": True,
        "date": datetime.now().isoformat(),
        "version": version,
    }
    fb_set("agreements", data)
