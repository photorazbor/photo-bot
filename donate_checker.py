"""
Проверка платежей DonatePay для автоматической активации курса
"""
import requests
import json
import os
import asyncio

DONATE_API = "https://donatepay.ru/api/v2/notifications"
ACCESS_TOKEN = "pytBdeWXxqGPKL0PW5jLL2QdKCLfDjSiL614W0bZbMehtBMSA7VhE31ylqRE"
CHECKED_FILE = "last_checked.json"

from course import activate_by_code


def get_last_id() -> int:
    if not os.path.exists(CHECKED_FILE):
        return 0
    with open(CHECKED_FILE, "r") as f:
        return json.load(f).get("last_id", 0)


def save_last_id(last_id: int):
    with open(CHECKED_FILE, "w") as f:
        json.dump({"last_id": last_id}, f)


def check_new_donations(bot=None):
    """Проверяет новые донаты и активирует курс."""
    try:
        last_id = get_last_id()
        params = {
            "access_token": ACCESS_TOKEN,
            "type": "donation",
            "order": "ASC",
            "after": last_id,
        }
        response = requests.get(DONATE_API, params=params, timeout=10)
        data = response.json()

        if "data" not in data:
            return

        for notification in data["data"]:
            nid = notification["id"]
            vars_data = notification.get("vars", {})
            amount = float(vars_data.get("amount", 0))
            comment = vars_data.get("comment", "")

            if amount >= 990:
                words = comment.split()
                for word in words:
                    if len(word) == 8 and word.isalnum():
                        user_id = activate_by_code(word)
                        if user_id and bot:
                            async def notify():
                                try:
                                    await bot.send_message(
                                        user_id,
                                        "✅ Твой платёж получен! Доступ к мини-курсу открыт.\nНапиши /course чтобы начать!"
                                    )
                                except:
                                    pass
                            try:
                                loop = asyncio.get_event_loop()
                                loop.create_task(notify())
                            except:
                                pass

            if nid > last_id:
                last_id = nid

        save_last_id(last_id)
    except Exception as e:
        print(f"Ошибка проверки донатов: {e}")


async def donate_poller(bot):
    """Фоновый опрос API DonatePay."""
    while True:
        check_new_donations(bot)
        await asyncio.sleep(30)