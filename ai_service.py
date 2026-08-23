"""
Обращение к Gemini Vision для анализа композиции фото и парсинг ответа
"""
import base64
import json
import re
import uuid
import requests
import os as _os
from datetime import datetime

from config import OPENAI_API_KEY, TOCHKA_API_TOKEN, SPESHU_API_KEY, KODIK_API_KEY, KODIK_BASE_URL

BASE_URL = "https://cheapai.io/v1"  # Старый CheapAI — не удаляем

PENDING_PAYMENTS_FILE = "pending_payments.json"

SYSTEM_PROMPT = """Ты --- наставник по мобильной фотографии. Живой стиль, лёгкий юмор, без сленга. Вдохновляешь снять круче.

Найди ВСЕ композиционные ошибки в этом кадре. Если кадр ОБЪЕКТИВНО ХОРОШ --- композиция грамотная, поза гармоничная, горизонт ровный, свет удачный, мусора нет --- НЕ придумывай ошибки. Вместо этого:
- Установи error_type = "good_shot"
- Напиши title = "Отличный кадр!"
- В what_is_wrong напиши "Я не нашёл композиционных ошибок --- кадр действительно хорош."
- В how_to_fix напиши "Переснимать не нужно. Разве что попробовать другой ракурс для интереса."
- В praise разверни: ЧТО ИМЕННО сделало кадр удачным (свет, поза, композиция, момент).
- В drawings оставь пустой массив [].

Если ошибки есть --- проверяй ВСЕГДА:
- Горизонт и геометрию --- ВАЖНО: не определяй завал по наклонным крышам, склонам гор или диагональным архитектурным элементам. ИЩИ ЧЁТКИЕ ОРИЕНТИРЫ: вертикальные объекты (столбы, кресты, памятники, углы зданий) и горизонтальные (линия водоёма, ровный пол, ступени). Если в кадре есть ЧЁТКАЯ ВЕРТИКАЛЬ (например, крест или столб), и она строго вертикальна --- горизонт НЕ завален, даже если крыши или горы идут под углом. Критикуй завал только если вертикали явно наклонены или линия водоёма уходит вбок.
- Правило третей (объект по центру --- не всегда ошибка, если выглядит осознанно). Если рекомендуешь сместить объект --- ОБЯЗАТЕЛЬНО добавляй grid_thirds в drawings.
- Ведущие линии и перспективу
- Фрейминг (арки, ветки, проёмы)
- Равновесие (не перевешивает ли кадр)
- Тень --- ОБЯЗАТЕЛЬНАЯ проверка. Отличай тень фотографа (короткая, прямо под ногами, явно от человека с камерой) от естественной тени объекта съёмки (длинная тень от человека на закате, тень от дерева, здания). Тень фотографа — ошибка. Естественная тень объекта — нормально, не ошибка. Если тень используется как художественный приём — отметь это в praise.
- Заполнение кадра и фон --- ВАЖНО: отличай «мусор» (случайные объекты, которые портят кадр: урны, провода, случайные прохожие) от «антуража» (интерьер, уличная сцена, детали, создающие атмосферу и историю). Если фон живой и добавляет колорит --- НЕ называй его ошибкой. Критикуй только явный мусор. Если рекомендуешь кадрирование --- ОБЯЗАТЕЛЬНО добавляй crop_frame в drawings.
- Искажения от широкого угла (отойти, снять на зум)
- Освещение (пересветы, провалы)

Поза человека (если есть) --- ОБЯЗАТЕЛЬНАЯ проверка. Даже если есть другие ошибки, проверь позу:
- Если человек стоит СТРОГО АНФАС — сначала оцени, выглядит ли это ОСОЗНАННО: минималистичный кадр, строгая симметрия, напряжённый взгляд в камеру, арт-портрет. Если да — отметь это как авторский замысел и НЕ называй ошибкой. Напиши: «Осознанный анфас — это работает как художественный приём».
- Если анфас — в большинстве случаев предложи разворот корпуса на 30-45°. Только если поза ЯВНО осознанная (арт-портрет с подчёркнутой симметрией, напряжённый взгляд, минимализм) — отметь как исключение.
- Сидит: колени не должны смотреть прямо в камеру — лучше диагональ.
- Проверь плечи, таз, суставы, взгляд.
- Если поза хорошая — напиши в praise о ней.

Арт-замысел: если кадр выглядит осознанным --- авторское видение сильнее правил. Отметь это. Если сомневаешься, ошибка это или замысел — считай ошибкой и предлагай исправление. Лучше указать на потенциальную проблему, чем пропустить её.

Формат: ТОЛЬКО валидный JSON, без markdown-блоков.
{
  "error_type": "horizon, thirds, leading_lines, framing, balance, shadow, fill_frame, distortion, pose, lighting, cropping, good_shot",
  "title": "Цепляющий заголовок",
  "what_is_wrong": "Что не так и почему. Если ошибок несколько --- упомяни их все. 2-3 предложения.",
  "how_to_fix": "Как переснять. 2-3 предложения.",
  "pro_tip": "Лайфхак профи. 1 предложение.",
  "praise": "Что получилось ХОРОШО. ОБЯЗАТЕЛЬНО найди хотя бы одну реально удачную деталь: свет, цвет, момент, композиционный приём, эмоцию, хорошую позу, атмосферный фон. Если фон создаёт атмосферу и историю --- похвали именно за это, а не критикуй. НЕ хвали за отсутствие тени --- это не достижение. Напиши 1-2 предложения, которые мотивируют ученика продолжать снимать.",
  "drawings": [
    {"type": "line", "x1": 0, "y1": 320, "x2": 1024, "y2": 380, "color": "red"}
  ]
}

Drawings (можно комбинировать несколько):
- line --- сплошная (горизонт, ведущие линии, плечи, таз).
- dashed_line --- пунктирная (правильный горизонт, линии сетки третей).
- crop_frame --- ЖЁЛТАЯ пунктирная рамка (yellow), показывающая предлагаемое кадрирование. ВСЁ ЧТО ЗА РАМКОЙ --- затемни (серый полупрозрачный слой, opacity 50%). Для crop_frame: x1,y1 --- верхний левый угол рамки, x2,y2 --- нижний правый.
- grid_thirds --- сетка правила третей: 2 горизонтальные + 2 вертикальные ТОНКИЕ БЕЛЫЕ полупрозрачные пунктирные линии (white), делящие кадр на 9 равных частей.
- circle --- эллипс (мусор в кадре, тень фотографа). Для circle: x1,y1 --- центр, x2,y2 --- радиус по X и Y.
- frame --- прямоугольник (зона правила третей, предлагаемое размещение объекта).
- arrow --- стрелка (куда смотреть, куда сместиться, куда развернуть модель). Для arrow: x1,y1 --- откуда, x2,y2 --- куда.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
- Если предлагаешь кадрирование --- ОБЯЗАТЕЛЬНО рисуй crop_frame (yellow).
- Если упоминаешь правило третей --- ОБЯЗАТЕЛЬНО рисуй grid_thirds (white).
- Если есть человек --- ОБЯЗАТЕЛЬНО line для плеч и line для таза.
- Если тень фотографа в кадре --- ОБЯЗАТЕЛЬНО circle.
- Если горизонт завален --- рисуй line по текущему (red) + dashed_line по правильному (green).
- Все координаты для фото 1024px по ширине. Y пересчитывай пропорционально реальной высоте.
- Цвета: red (проблема), green (правильно), yellow (кадрирование), white (сетка третей).
"""


def _image_bytes_to_data_url(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    if not text.startswith("{"):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    return json.loads(text)


def _load_pending_payments() -> dict:
    if not _os.path.exists(PENDING_PAYMENTS_FILE):
        return {}
    with open(PENDING_PAYMENTS_FILE, "r") as f:
        return json.load(f)


def _save_payment_link(payment_link_id: str, user_id: int, purpose: str):
    """Сохраняет информацию о платеже для последующего начисления."""
    pending = _load_pending_payments()
    pending[payment_link_id] = {
        "user_id": user_id,
        "purpose": purpose,
        "created": datetime.now().isoformat()
    }
    with open(PENDING_PAYMENTS_FILE, "w") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def analyze_photo(image_bytes: bytes, course_topic: str = None) -> dict:
    data_url = _image_bytes_to_data_url(image_bytes)

    if course_topic:
        system_prompt = f"""Ты --- преподаватель фотографии. Ты проверяешь домашнее задание.

Тема задания: {course_topic}

ПРАВИЛА ПРОВЕРКИ (реалистичные, не идеальные):
- Если тема «Горизонт и геометрия»: горизонт должен быть достаточно ровным (небольшой наклон в 1-2 градуса допустим). Явный завал (видно глазом) --- НЕВЫПОЛНЕНИЕ.
- Если тема «Правило третей»: объект должен быть ЯВНО смещён от центра, с воздухом по направлению взгляда. Не требую идеального попадания на линию трети. Объект строго по центру и без воздуха --- НЕВЫПОЛНЕНИЕ.
- Если тема «Поза человека»: модель не должна стоять СТРОГО анфас. Небольшой разворот или диагональ уже считается выполнением. Полный анфас с коленями в камеру --- НЕВЫПОЛНЕНИЕ.
- Если тема «Свет и тени»: свет не должен быть фронтальным (вспышка в лоб). Боковой, контровой или просто мягкий рассеянный свет --- ВЫПОЛНЕНИЕ. Плоский передний свет --- НЕВЫПОЛНЕНИЕ.
- Если тема «Тень как приём»: тень должна быть заметной и работать на кадр (даже просто длинная тень от дерева). Случайная невыразительная тень --- НЕВЫПОЛНЕНИЕ.
- Если тема «Отражения»: отражение должно быть ЗАМЕТНО и участвовать в композиции. Небольшое отражение в луже или окне --- уже ВЫПОЛНЕНИЕ. Нет отражения --- НЕВЫПОЛНЕНИЕ.
- Если тема «Фрейминг»: должна быть естественная рамка (арка, окно, ветки). Нет рамки --- НЕВЫПОЛНЕНИЕ.
- Если тема «Ритм и перспектива»: должны быть повторяющиеся элементы, уходящие вдаль. Нет повторов или перспективы --- НЕВЫПОЛНЕНИЕ.
- Если тема «Глубина кадра»: должны читаться три плана (передний, средний, задний). Плоский кадр без глубины --- НЕВЫПОЛНЕНИЕ.

Вердикт:
- Задание ВЫПОЛНЕНО только если приём применён ПРАВИЛЬНО (по реалистичным критериям выше). Тогда error_type = "good_shot".
- Если есть ошибка по теме --- error_type = "topic_error". НЕ ставь good_shot, если есть сомнения.

Также отметь, что получилось хорошо (praise), и что можно улучшить по теме (what_is_wrong, how_to_fix). Нарисуй drawings с ошибкой, если она есть.

Формат: ТОЛЬКО JSON.
{{
  "error_type": "good_shot или topic_error",
  "title": "Задание: {course_topic}",
  "what_is_wrong": "Конкретно по теме: что не так и почему. Если задание НЕ выполнено --- напиши 'Задание не выполнено' в начале. Если выполнено --- напиши 'Задание выполнено'.",
  "how_to_fix": "Как исправить.",
  "pro_tip": "Один совет.",
  "praise": "Что хорошо. Поддержи. Даже если задание не выполнено.",
  "drawings": [
    {{"type": "line", "x1": 0, "y1": 320, "x2": 1024, "y2": 380, "color": "red"}}
  ]
}}

Drawings: line, dashed_line, circle, frame, arrow, grid_thirds, crop_frame.
Координаты для фото 1024px. Цвета: red (проблема), green (правильно).
"""
    else:
        system_prompt = SYSTEM_PROMPT

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gemini-3.5-flash",
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 1000,
    }

    response = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        print(f"Ошибка API: {response.status_code} {response.text}")
        return None

    raw_text = response.json()["choices"][0]["message"]["content"]

    try:
        return _extract_json(raw_text)
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Не удалось распарсить JSON: {e}\nОтвет модели: {raw_text}")
        return None


def generate_image(image_bytes: bytes, prompt: str) -> bytes | None:
    """Генерирует изображение через Gemini Image API на CheapAI (Формат 1)."""
    data_url = _image_bytes_to_data_url(image_bytes)

    headers = {
        "Authorization": f"Bearer {KODIK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gemini-3.1-flash-image-preview",
        "modalities": ["image", "text"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 2000,
    }

    response = requests.post(f"{KODIK_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=45)

    # if response.status_code != 200:
    #     print("CheapAI не ответил, пробую SpeShu...")
    #     spe_shu_headers = {
    #         "Authorization": f"Bearer {SPESHU_API_KEY}",
    #         "Content-Type": "application/json"
    #     }
    #     spesh_task = requests.post(
    #         "https://speshu.ai/api/v1/async/media/tasks",
    #         headers=spe_shu_headers,
    #         json={
    #             "model": "nano-banana-2",
    #             "input": {
    #                 "prompt": prompt,
    #                 "images": [{"type": "url", "data": data_url}]
    #             }
    #         },
    #         timeout=45
    #     )
    #     if spesh_task.status_code not in (200, 201):
    #         print(f"Ошибка SpeShu: {spesh_task.status_code} {spesh_task.text}")
    #         return None
    # 
    #     task_id = spesh_task.json().get("data", {}).get("taskId")
    #     if not task_id:
    #         print("Нет taskId от SpeShu")
    #         return None
    # 
    #     import time
    #     for _ in range(60):
    #         time.sleep(3)
    #         spesh_result = requests.get(
    #             f"https://speshu.ai/api/v1/async/media/tasks/{task_id}",
    #             headers=spe_shu_headers,
    #             timeout=30
    #         )
    #         if spesh_result.status_code == 200:
    #             result_data = spesh_result.json().get("data", {})
    #             status = result_data.get("status")
    #             if status == "success":
    #                 result_json = result_data.get("resultJson", {})
    #                 image_url = result_json.get("url") or result_json.get("image_url") or result_json.get("output")
    #                 if image_url:
    #                     image_response = requests.get(image_url, timeout=45)
    #                     if image_response.status_code == 200:
    #                         return image_response.content
    #                 break
    #             elif status == "fail":
    #                 print(f"SpeShu fail: {result_data.get('failMsg')}")
    #                 break
    #     print("SpeShu не вернул результат")
    #     return None

    result = response.json()
    try:
        content = result["choices"][0]["message"]["content"]

        match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
        if match:
            b64_str = match.group(1)
            return base64.b64decode(b64_str)

        if content.startswith("iVBOR") or content.startswith("/9j/"):
            return base64.b64decode(content)

        print(f"Не удалось извлечь изображение из ответа: {content[:200]}...")
        return None

    except Exception as e:
        print(f"Не удалось извлечь изображение: {e}")
        return None


def create_payment_link(amount: float, purpose: str, user_id: int = None) -> str | None:
    if not TOCHKA_API_TOKEN:
        print("Ошибка: TOCHKA_API_TOKEN не задан в config.py")
        return None

    url = "https://enter.tochka.com/uapi/acquiring/v1.0/payments"

    payment_link_id = str(uuid.uuid4())

    payload = {
        "Data": {
            "customerCode": "301511177",
            "merchantId": "200000000041437",
            "amount": f"{amount:.2f}",
            "purpose": purpose,
            "redirectUrl": "https://t.me/moy_razbor_bot",
            "failRedirectUrl": "https://t.me/moy_razbor_bot",
            "webhookUrl": "https://photo-bot-6koz.onrender.com/webhook/tochka",
            "paymentMode": ["sbp", "card"],
            "saveCard": False,
            "preAuthorization": False,
            "ttl": 10080,
            "paymentLinkId": payment_link_id
        }
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {TOCHKA_API_TOKEN}'
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code not in (200, 201):
            print(f"Ошибка API Точки: {response.status_code} {response.text[:300]}")
            return None
        data = response.json()
        payment_link = data.get("Data", {}).get("paymentLink")
        if payment_link and user_id:
            _save_payment_link(payment_link_id, user_id, purpose)
        if payment_link:
            return payment_link
        else:
            print(f"В ответе нет paymentLink: {data}")
            return None
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None
