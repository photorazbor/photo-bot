"""
Загрузка переменных окружения (токены API)
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except (ImportError, FileNotFoundError):
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOCHKA_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmM2VkODE2MjA2NDYwODBjNjZlYjZhZjFhYzViZGRlNiIsInN1YiI6ImNkN2I4OTc2LTM2MTQtNGVkNi05MTFlLTExM2ZmNmMyZjBiMyIsImN1c3RvbWVyX2NvZGUiOiIzMDEyODAwNzUifQ.kTtufFmVXtg5z46gP70mpDOBqnr_1YfBiFB_N0VbrNMCd4KkzDVyoh5yMYCUqddwhRueAG8TP5YXC9fq0ofdbGCtET_kJw9TDUXlYaLaHgLXfrrpqMCIQed4h8pebUB5noA6_j6csfO_JgPQ830pDniTMyfeDQLpOedYHOcwy-SfX_Ya0miMcF8EFIxrzNWBXbKJ1OjE8xpVK0ftTTpwDehrKaJ2D5PT1tLOpYbVImj5ZCbijMzETcc71TcawLwPJXUDE_9jhnSBr4qEkPDXjA-l8Gmeak6gvOd2vSK1esmQcP7i3bOvZ07k4RjkZ8Ea6QArSGF8jvqx-leSPwb_nWHSznrCX-KXc_pJZt7zdP75GyjXYKGzAE3amxWl7mRTq1DdkGR2eOVvcnquJKO5VDJQNQaJCnRSdCa58Hq50Y0OwrLSwdTFObF9GFunErtPO4gaJ5Y4jZ3AVCDyb1TgE-V0mE50WjuVMHrEjzUaHTXqWmSHmBb7xudbiPZoXB2l"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY")
