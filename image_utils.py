"""
Работа с изображениями: скачивание, сжатие и рисование подсказок поверх фото
"""
import io
import math
import random
import requests
from PIL import Image, ImageDraw, ImageFilter


def download_and_resize(photo_url: str, target_width: int = 1024) -> Image.Image:
    """
    Скачивает фото по URL и сжимает его до target_width по ширине,
    сохраняя пропорции. Возвращает объект PIL.Image в режиме RGB.
    """
    response = requests.get(photo_url, timeout=30)
    response.raise_for_status()

    image = Image.open(io.BytesIO(response.content)).convert("RGB")

    width, height = image.size
    if width > target_width:
        ratio = target_width / width
        new_height = int(height * ratio)
        image = image.resize((target_width, new_height), Image.LANCZOS)

    return image


def image_to_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    """Превращает PIL.Image в байты для отправки в Telegram или сохранения."""
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=90)
    return buffer.getvalue()


def _hex_to_rgb(hex_color: str) -> tuple:
    """Переводит HEX в RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _draw_solid_line(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=5, opacity=255):
    """Рисует яркую сплошную линию."""
    rgba_color = (*_hex_to_rgb(color), opacity)

    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.line([(x1, y1), (x2, y2)], fill=rgba_color, width=width)

    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_dashed_line(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=2, dash=12, gap=8, opacity=210):
    """Рисует стильную пунктирную линию."""
    rgba_color = (*_hex_to_rgb(color), opacity)
    total_length = math.hypot(x2 - x1, y2 - y1)
    if total_length == 0:
        return
    dx = (x2 - x1) / total_length
    dy = (y2 - y1) / total_length

    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    distance = 0
    while distance < total_length:
        start_x = x1 + dx * distance
        start_y = y1 + dy * distance
        end_distance = min(distance + dash, total_length)
        end_x = x1 + dx * end_distance
        end_y = y1 + dy * end_distance
        overlay_draw.line([(start_x, start_y), (end_x, end_y)], fill=rgba_color, width=width)
        distance += dash + gap

    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_arrow(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=5, head_size=18, opacity=255):
    """Рисует стрелку с треугольным наконечником."""
    rgba_color = (*_hex_to_rgb(color), opacity)

    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    overlay_draw.line([(x1, y1), (x2, y2)], fill=rgba_color, width=width)

    angle = math.atan2(y2 - y1, x2 - x1)
    left_angle = angle + math.radians(150)
    right_angle = angle - math.radians(150)

    left_point = (x2 + head_size * math.cos(left_angle), y2 + head_size * math.sin(left_angle))
    right_point = (x2 + head_size * math.cos(right_angle), y2 + head_size * math.sin(right_angle))

    overlay_draw.polygon([(x2, y2), left_point, right_point], fill=rgba_color)

    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_crop_frame(draw: ImageDraw.ImageDraw, image: Image.Image, x1, y1, x2, y2, color="#FFDD00"):
    """Рисует жёлтую пунктирную рамку кадрирования и затемняет область за ней."""
    width, height = image.size

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    if y1 > 0:
        overlay_draw.rectangle([(0, 0), (width, y1)], fill=(0, 0, 0, 100))
    if y2 < height:
        overlay_draw.rectangle([(0, y2), (width, height)], fill=(0, 0, 0, 100))
    if x1 > 0:
        overlay_draw.rectangle([(0, y1), (x1, y2)], fill=(0, 0, 0, 100))
    if x2 < width:
        overlay_draw.rectangle([(x2, y1), (width, y2)], fill=(0, 0, 0, 100))

    image_rgba = image.convert("RGBA")
    image_rgba = Image.alpha_composite(image_rgba, overlay)
    image_rgba = image_rgba.convert("RGB")
    image.paste(image_rgba)

    draw = ImageDraw.Draw(image)
    _draw_dashed_line(draw, x1, y1, x2, y1, color, width=3, dash=15, gap=8, opacity=220)
    _draw_dashed_line(draw, x1, y2, x2, y2, color, width=3, dash=15, gap=8, opacity=220)
    _draw_dashed_line(draw, x1, y1, x1, y2, color, width=3, dash=15, gap=8, opacity=220)
    _draw_dashed_line(draw, x2, y1, x2, y2, color, width=3, dash=15, gap=8, opacity=220)


def _draw_grid_thirds(draw: ImageDraw.ImageDraw, image: Image.Image, color="#FFFFFF"):
    """Рисует сетку правила третей: тонкие полупрозрачные пунктирные линии."""
    width, height = image.size
    third_h = height // 3
    third_w = width // 3

    _draw_dashed_line(draw, 0, third_h, width, third_h, color, width=2, dash=20, gap=12, opacity=180)
    _draw_dashed_line(draw, 0, third_h * 2, width, third_h * 2, color, width=2, dash=20, gap=12, opacity=180)
    _draw_dashed_line(draw, third_w, 0, third_w, height, color, width=2, dash=20, gap=12, opacity=180)
    _draw_dashed_line(draw, third_w * 2, 0, third_w * 2, height, color, width=2, dash=20, gap=12, opacity=180)


def _draw_marker_circle(draw: ImageDraw.ImageDraw, x1, y1, rx, ry, color="#FFB74D", width=6, opacity=255):
    """Рисует яркий замкнутый эллипс."""
    rgba_color = (*_hex_to_rgb(color), opacity)

    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    bbox = [(x1 - rx, y1 - ry), (x1 + rx, y1 + ry)]
    overlay_draw.ellipse(bbox, outline=rgba_color, width=width)

    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_marker_rect(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color="#FFB74D", width=6, opacity=255):
    """Рисует яркий замкнутый прямоугольник."""
    rgba_color = (*_hex_to_rgb(color), opacity)

    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    overlay_draw.rectangle([(x1, y1), (x2, y2)], outline=rgba_color, width=width)

    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def draw_hints(image: Image.Image, drawings: list) -> Image.Image:
    """
    Рисует поверх фото список подсказок (линии, круги, рамки, стрелки),
    полученных от ИИ. Стиль — яркий маркерный, без дрожания.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    for item in drawings:
        shape_type = item.get("type")
        color = item.get("color", "#FF2222")
        x1, y1 = item.get("x1", 0), item.get("y1", 0)
        x2, y2 = item.get("x2", 0), item.get("y2", 0)

        if color == "red":
            color = "#FF2222"
        elif color == "green":
            color = "#00DD00"
        elif color == "yellow":
            color = "#FFDD00"
        elif color == "white":
            color = "#FFFFFF"

        try:
            if shape_type == "line":
                _draw_solid_line(draw, x1, y1, x2, y2, color, width=5, opacity=255)
            elif shape_type == "dashed_line":
                _draw_dashed_line(draw, x1, y1, x2, y2, color, width=4, dash=12, gap=8, opacity=240)
            elif shape_type == "crop_frame":
                _draw_crop_frame(draw, result, x1, y1, x2, y2, color)
            elif shape_type == "grid_thirds":
                _draw_grid_thirds(draw, result, color)
            elif shape_type == "circle":
                rx, ry = x2, y2
                _draw_marker_circle(draw, x1, y1, rx, ry, "#FFB74D", width=6, opacity=255)
            elif shape_type == "frame":
                _draw_marker_rect(draw, x1, y1, x2, y2, "#FFB74D", width=6, opacity=255)
            elif shape_type == "arrow":
                _draw_arrow(draw, x1, y1, x2, y2, color, width=5, opacity=255)
        except Exception as e:
            print(f"Не удалось нарисовать {shape_type}: {e}")
            continue

    return result


# ===== ВЫРАВНИВАНИЕ ИНТЕРЬЕРА =====
import numpy as np


def align_interior(image: Image.Image) -> Image.Image:
    """Простое выравнивание через deskew."""
    try:
        from deskew import determine_skew
        from scipy.ndimage import rotate as scipy_rotate
        
        img = np.array(image)
        angle = determine_skew(img)
        
        # Мягкое выравнивание
        if abs(angle) < 0.5:
            return image
        
        # Не переусердствуем
        angle = angle * 2.5
        
        rotated = scipy_rotate(img, angle, reshape=False, mode='nearest')
        return Image.fromarray(rotated)
    except Exception as e:
        print(f"Ошибка выравнивания: {e}")
        return image


import os
import cv2
import numpy as np


# ===== ФОТО НА ДОКУМЕНТЫ (ГОСТ) =====

def prepare_doc_photo(image_bytes: bytes, doc_type: str = "passport") -> bytes:
    """
    Подгоняет фото под ГОСТ Р 52112-2003:
    - 35×45 мм (413×531 px @ 300 DPI)
    - Голова: 70-80% высоты (29-34 мм)
    - Лицо по центру
    - Отступ макушки: 5-7 мм
    - Белый фон
    """
    try:
        # 1. Загружаем фото
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        
        height, width = img.shape[:2]
        
        # 2. Детекция лица
        face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        if face_cascade.empty():
            print("❌ Не удалось загрузить haarcascade_frontalface_default.xml")
            return image_bytes
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100)
        )
        
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(80, 80)
            )
        
        if len(faces) == 0:
            print("❌ Лицо не найдено")
            return image_bytes
        
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        fx, fy, fw, fh = faces[0]
        
        face_center_x = fx + fw // 2
        face_center_y = fy + fh // 2
        
        TOP_MARGIN_RATIO = 0.13
        
        head_top = fy - int(fh * 0.35)
        head_bottom = fy + fh
        head_height = head_bottom - head_top
        
        crop_height = int(head_height / 0.71)
        crop_width = int(crop_height * 35 / 45)
        
        crop_y1 = head_top - int(crop_height * TOP_MARGIN_RATIO)
        crop_x1 = face_center_x - crop_width // 2
        
        crop_y1 = max(0, crop_y1)
        crop_x1 = max(0, crop_x1)
        
        if crop_y1 + crop_height > height:
            crop_y1 = height - crop_height
        if crop_x1 + crop_width > width:
            crop_x1 = width - crop_width
        
        if crop_y1 < 0 or crop_x1 < 0 or crop_width > width or crop_height > height:
            scale = max(crop_width / width, crop_height / height) * 1.2
            new_w = int(width * scale)
            new_h = int(height * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
            if len(faces) == 0:
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(80, 80))
            if len(faces) == 0:
                return image_bytes
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            fx, fy, fw, fh = faces[0]
            face_center_x = fx + fw // 2
            face_center_y = fy + fh // 2
            head_top = fy - int(fh * 0.35)
            head_bottom = fy + fh
            head_height = head_bottom - head_top
            crop_height = int(head_height / 0.71)
            crop_width = int(crop_height * 35 / 45)
            crop_y1 = max(0, head_top - int(crop_height * TOP_MARGIN_RATIO))
            crop_x1 = max(0, face_center_x - crop_width // 2)
            if crop_y1 + crop_height > img.shape[0]:
                crop_y1 = img.shape[0] - crop_height
            if crop_x1 + crop_width > img.shape[1]:
                crop_x1 = img.shape[1] - crop_width
        
        cropped = img[crop_y1:crop_y1 + crop_height, crop_x1:crop_x1 + crop_width]
        
        result = cv2.resize(cropped, (413, 531), interpolation=cv2.INTER_LANCZOS4)
        
        borders = [
            result[0:10, :],
            result[-10:, :],
            result[:, 0:10],
            result[:, -10:],
        ]
        avg_brightness = np.mean([np.mean(b) for b in borders])
        
        if avg_brightness < 240:
            result = _whiten_background(result)
        
        _, buffer = cv2.imencode(".jpg", result, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()
    
    except Exception as e:
        print(f"❌ Ошибка prepare_doc_photo: {e}")
        return image_bytes


def crop_doc_custom(image_bytes: bytes, head_ratio: float = 0.71, shift_y: float = 0.0) -> bytes:
    """
    Кадрирует фото по ГОСТу с заданными параметрами.
    head_ratio: 0.71 = стандарт, 0.78 = крупнее
    shift_y: сдвиг кадра по вертикали
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        
        face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        if face_cascade.empty():
            return image_bytes
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(80, 80))
        if len(faces) == 0:
            return image_bytes
        
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        fx, fy, fw, fh = faces[0]
        face_center_x = fx + fw // 2
        
        head_top = fy - int(fh * 0.35)
        head_bottom = fy + fh
        head_height = head_bottom - head_top
        
        crop_height = int(head_height / head_ratio)
        crop_width = int(crop_height * 35 / 45)
        
        crop_y1 = head_top - int(crop_height * 0.13)
        crop_x1 = face_center_x - crop_width // 2
        
        if shift_y != 0:
            shift_px = int(crop_height * shift_y)
            crop_y1 += shift_px
        
        crop_y1 = max(0, min(crop_y1, img.shape[0] - crop_height))
        crop_x1 = max(0, min(crop_x1, img.shape[1] - crop_width))
        
        cropped = img[crop_y1:crop_y1 + crop_height, crop_x1:crop_x1 + crop_width]
        result = cv2.resize(cropped, (413, 531), interpolation=cv2.INTER_LANCZOS4)
        
        _, buffer = cv2.imencode(".jpg", result, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()
    
    except Exception as e:
        print(f"❌ Ошибка crop_doc_custom: {e}")
        return image_bytes



def _whiten_background(img: np.ndarray) -> np.ndarray:
    """
    Отбеливает фон: всё, что светлее порога, становится белым.
    Лицо (тёмное) остаётся.
    """
    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        lower = np.array([0, 0, 200])
        upper = np.array([180, 50, 255])
        mask = cv2.inRange(hsv, lower, upper)
        
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        img[mask > 0] = [255, 255, 255]
        
        img = cv2.GaussianBlur(img, (3, 3), 0)
        
        return img
    except Exception as e:
        print(f"❌ Ошибка отбеливания: {e}")
        return img


def draw_gost_guide(image_bytes: bytes) -> bytes:
    """
    Рисует направляющие линии ГОСТа поверх фото.
    Зелёный пунктирный овал головы + линии глаз и подбородка.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        
        h, w = img.shape[:2]
        
        HEAD_TOP = 60
        HEAD_BOTTOM = 400
        HEAD_HEIGHT = 340
        HEAD_WIDTH = 220
        HEAD_LEFT = (w - HEAD_WIDTH) // 2
        HEAD_RIGHT = HEAD_LEFT + HEAD_WIDTH
        EYE_LINE = 247
        CENTER_X = w // 2
        CENTER_Y = (HEAD_TOP + HEAD_BOTTOM) // 2
        
        for angle in range(0, 360, 15):
            start_angle = angle
            end_angle = angle + 8
            cv2.ellipse(
                img,
                (CENTER_X, CENTER_Y),
                (HEAD_WIDTH // 2, HEAD_HEIGHT // 2),
                0,
                start_angle,
                end_angle,
                (0, 255, 0),
                3
            )
        
        for x in range(HEAD_LEFT, HEAD_RIGHT, 20):
            cv2.line(img, (x, EYE_LINE), (x + 10, EYE_LINE), (0, 255, 0), 3)
        
        for x in range(HEAD_LEFT, HEAD_RIGHT, 20):
            cv2.line(img, (x, HEAD_BOTTOM), (x + 10, HEAD_BOTTOM), (0, 255, 0), 3)
        
        for y in range(HEAD_TOP, HEAD_BOTTOM, 20):
            cv2.line(img, (CENTER_X, y), (CENTER_X, y + 10), (0, 255, 0), 2)
        
        _, buffer = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()
    
    except Exception as e:
        print(f"❌ Ошибка draw_gost_guide: {e}")
        return image_bytes


def check_and_crop_doc_photo(image_bytes: bytes, doc_type: str = "passport") -> bytes:
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        height, width = img.shape[:2]

        if doc_type == "passport":
            new_h = int(height * 0.82)
            cropped = img[:new_h, :]
            target_ratio = 35 / 45
            new_w = int(new_h * target_ratio)
            if new_w <= width:
                start_x = (width - new_w) // 2
                cropped = cropped[:, start_x:start_x + new_w]
        else:
            cropped = img

        _, buffer = cv2.imencode(".jpg", cropped, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()

    except Exception as e:
        print(f"Ошибка: {e}")
        return image_bytes
