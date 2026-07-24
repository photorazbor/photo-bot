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
TOCHKA_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIzMTFjMzNmYmYzOTE2OGQ5NWU4NGQ0M2JjYjc5Mzc5ZCIsInN1YiI6ImNkN2I4OTc2LTM2MTQtNGVkNi05MTFlLTExM2ZmNmMyZjBiMyIsImN1c3RvbWVyX2NvZGUiOiIzMDEyODAwNzUifQ.WI29D3f4lQb4L_Vj3wTO1qQC08Azyv1-ds_gk8IrS8eyyl4Jbvua7AzNy-Og5Nt7DaFp5rnfmtvJIeB1mYzb6UJFfdsx9gO7m7FDRvFbDazO5GNoiIVrtxWNhxUnFbGj5mbBWNwIZJ21UM4ruM61Y60p2NAO43nD2_7TbcOGQKLZ6QeIty7P8tAYBwZkWIKSKj_DxslmFKnCj7RE6x9fPSsDKQxhlszCtaHGeWj0_Bjbk9QpB4BbqpZIYN8s1qAfOFCnjuTDZSyTkbReyx3PdHVpcBsUKNG1S_5HjocQu0D96Hza5UBbNqcoaO4zzCU3Bmuo349DekZVSnPUuJwDdZn3CkzpmxHUaiyP7xJ1rKXpc55XyrAMZPfVp56PIFtm162Kh5zoJybt1RPXXX4VF9isfH-CZ4Y7kkomjfWEjVe36QPrZxEjf9Ja7LGWFEjjrW9uL20ArfKVsJtBb0GWV9sVSnkTsxY2gXrzP7rMynPwQeR2KjU6-RibhIDTi4g2"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY")
