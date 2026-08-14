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
SPESHU_API_KEY = "sk-19b67b5c-ddbc-462e-b3a3-37ec9188df99"
TOCHKA_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1ZTNmODhjMTI2OTBiMzA4NmZhZjdmYTBkYWY0NmVmYSIsInN1YiI6ImNkN2I4OTc2LTM2MTQtNGVkNi05MTFlLTExM2ZmNmMyZjBiMyIsImN1c3RvbWVyX2NvZGUiOiIzMDEyODAwNzUifQ.BINqbZl-eaGyBb9YWU5_2h7kQLXCLyX44w6uuKSeG7ciB_i4ixu0WRjyf-i0Ya1qPHL8lIKBq0ZR7qaJT55xRAYCyVorvEdXZiLpolBlDyye2GXCqHk5oWx8MGws93psYAW4b-TFDRDUbNiERj2myv1LO88xEW3fcgwLVzHLCFDLPXPATSOB8LqqRKcJe_oVC42LJ5j4B-CI9WTnWDyVeu03pEEEDxDXWj0-b3v64iT45eN2clU7r74djKbfGjHzoq-e8p2V2Uu2Sdf5Xr8WjSxdv2Q9aHv6q9-jwhtSM3GEp722c6yAdGkyz8X8K_P6H2jmSeiO0__ppuYj9XbWqgCr_kqJIcs4yOqXt4bfWCSh9Mm1XIe5dDs4JbbCRRVEYLnBsqWpC-Mq_VZRvpWq8r_IpLG5BU3ZuYdx7rKHqydTlFhAfbXmm5UueCbaqKrBYCNiz7Z9y9mBVYQSJ6vYOUPA52B1kFwa3XWJGqKuuldY40oB-cfDNuMvVFey3lM5"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY")
