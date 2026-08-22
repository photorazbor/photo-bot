"""
Работа с изображениями: скачивание, сжатие и рисование подсказок поверх фото
"""
import io
import math
import random
import requests
from PIL import Image, ImageDraw


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

        # Яркие маркерные цвета
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

import cv2
import numpy as np

def align_interior(image: Image.Image) -> Image.Image:
    """Выравнивает вертикали и горизонтали на фото интерьера."""
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
    
    if lines is None:
        return image
    
    vertical_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.degrees(np.arctan2(y2-y1, x2-x1)))
        if 70 < angle < 110:
            vertical_lines.append((x1, y1, x2, y2))
    
    if not vertical_lines:
        return image
    
    angles = []
    for x1, y1, x2, y2 in vertical_lines[:5]:
        angle = np.degrees(np.arctan2(x2-x1, y2-y1))
        angles.append(angle)
    
    avg_angle = np.mean(angles)
    
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, avg_angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    
    return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
