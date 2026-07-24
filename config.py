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
TOCHKA_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlYjFiNzBlMTgyOTM2ODAxYzE5OTJiZTMzZmY5MGI3OCIsInN1YiI6ImNkN2I4OTc2LTM2MTQtNGVkNi05MTFlLTExM2ZmNmMyZjBiMyIsImN1c3RvbWVyX2NvZGUiOiIzMDEyODAwNzUifQ.Z5SfIEa69iMGuFN4R_loiB6PSTnC06hnoL6yF4kqYB42DeGThI3NXdkKoniblMU7Fx41LZzQoNbP_dhS9NffCGVRx6l3q1hVb35pAFaes02BgSZjlhn6ngEymr8hp52xT7uI_CY-em3rACl42cCr8mUKDr6zMVtODsFglovbh7cuxHMQBjWeQRoGsxPgRTl1a7xORC8EXyz9bHYHtbyK2fyUu8yBF8z1uNHaZ1Zi8DGrGkPTIlshd6tSpDIfkJ8cXerPEy5jKQvmcwqnk7mDDwBFYaF_CotrtyUq6elwMZAu6_niVVGqig2PZzeMyQNWVjB6QgFzIJ05an-LuRGY3T27taIFUV3u3IDw1yvcsTr201LMGMO8y4W4D0HeeXSgIkhRwlJkXTBlb1BkYsneb10JLhlWE4vCyN_ua9WN3YDs1uN9Y_arTQWNolrgoeRSM7322egpus0v7VCXacQIr-Zikaxlk_VW4cgKxoRLofrC0uLcqOj8sR4fe7uGTsbe"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY")
