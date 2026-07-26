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


def _jitter(coord: int, amount: int = 2) -> int:
    """Добавляет лёгкое дрожание для имитации рисования от руки."""
    return coord + random.randint(-amount, amount)


def _hex_to_rgb(hex_color: str) -> tuple:
    """Переводит HEX в RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _draw_line_handdrawn(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=3, opacity=230):
    """Рисует линию с лёгким дрожанием."""
    rgba_color = (*_hex_to_rgb(color), opacity)
    points = [(x1, y1)]
    steps = max(int(math.hypot(x2 - x1, y2 - y1) / 10), 1)
    for i in range(1, steps):
        t = i / steps
        px = x1 + (x2 - x1) * t + random.randint(-2, 2)
        py = y1 + (y2 - y1) * t + random.randint(-2, 2)
        points.append((px, py))
    points.append((x2, y2))
    
    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(len(points) - 1):
        overlay_draw.line([points[i], points[i+1]], fill=rgba_color, width=width)
    
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


def _draw_arrow(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=3, head_size=15, opacity=230):
    """Рисует стрелку с треугольным наконечником."""
    rgba_color = (*_hex_to_rgb(color), opacity)
    
    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Линия
    overlay_draw.line([(x1, y1), (x2, y2)], fill=rgba_color, width=width)

    # Наконечник
    angle = math.atan2(y2 - y1, x2 - x1)
    left_angle = angle + math.radians(150)
    right_angle = angle - math.radians(150)

    left_point = (x2 + head_size * math.cos(left_angle), y2 + head_size * math.sin(left_angle))
    right_point = (x2 + head_size * math.cos(right_angle), y2 + head_size * math.sin(right_angle))

    overlay_draw.polygon([(x2, y2), left_point, right_point], fill=rgba_color)
    
    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_crop_frame(draw: ImageDraw.ImageDraw, image: Image.Image, x1, y1, x2, y2, color="#FFD54F"):
    """Рисует жёлтую пунктирную рамку кадрирования и затемняет область за ней."""
    width, height = image.size

    # Затемняем область за рамкой
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

    # Жёлтая пунктирная рамка
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


def _draw_marker_arc(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color="#FFB74D", width=4, opacity=230):
    """Рисует незамкнутую дугу — имитация обводки маркером."""
    rgba_color = (*_hex_to_rgb(color), opacity)
    
    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Рисуем 4 угла как дуги, но не замыкаем прямоугольник полностью
    gap = 30  # Разрыв в углах для эффекта скобок
    
    # Верхняя линия
    overlay_draw.line([(x1 + gap, y1), (x2 - gap, y1)], fill=rgba_color, width=width)
    # Правая линия
    overlay_draw.line([(x2, y1 + gap), (x2, y2 - gap)], fill=rgba_color, width=width)
    # Нижняя линия
    overlay_draw.line([(x2 - gap, y2), (x1 + gap, y2)], fill=rgba_color, width=width)
    # Левая линия
    overlay_draw.line([(x1, y2 - gap), (x1, y1 + gap)], fill=rgba_color, width=width)
    
    # Маленькие закругления на углах
    overlay_draw.arc([(x1 - 5, y1 - 5), (x1 + gap + 5, y1 + gap + 5)], 180, 270, fill=rgba_color, width=width)
    overlay_draw.arc([(x2 - gap - 5, y1 - 5), (x2 + 5, y1 + gap + 5)], 270, 360, fill=rgba_color, width=width)
    overlay_draw.arc([(x2 - gap - 5, y2 - gap - 5), (x2 + 5, y2 + 5)], 0, 90, fill=rgba_color, width=width)
    overlay_draw.arc([(x1 - 5, y2 - gap - 5), (x1 + gap + 5, y2 + 5)], 90, 180, fill=rgba_color, width=width)
    
    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def _draw_marker_circle(draw: ImageDraw.ImageDraw, x1, y1, rx, ry, color="#FFB74D", width=4, opacity=230):
    """Рисует незамкнутый эллипс — имитация обводки маркером."""
    rgba_color = (*_hex_to_rgb(color), opacity)
    
    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Рисуем почти полный эллипс с разрывом
    bbox = [(x1 - rx, y1 - ry), (x1 + rx, y1 + ry)]
    overlay_draw.arc(bbox, 30, 330, fill=rgba_color, width=width)
    
    # Лёгкие штрихи на концах для имитации маркера
    angle_start = math.radians(30)
    angle_end = math.radians(330)
    
    start_x = x1 + rx * math.cos(angle_start)
    start_y = y1 + ry * math.sin(angle_start)
    end_x = x1 + rx * math.cos(angle_end)
    end_y = y1 + ry * math.sin(angle_end)
    
    overlay_draw.line([(start_x - 5, start_y - 5), (start_x, start_y)], fill=rgba_color, width=width - 1)
    overlay_draw.line([(end_x, end_y), (end_x + 5, end_y - 5)], fill=rgba_color, width=width - 1)
    
    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), overlay).convert("RGB"))


def draw_hints(image: Image.Image, drawings: list) -> Image.Image:
    """
    Рисует поверх фото список подсказок (линии, круги, рамки, стрелки),
    полученных от ИИ. Стиль — живой, маркерный, современный.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    for item in drawings:
        shape_type = item.get("type")
        color = item.get("color", "#E57373")  # По умолчанию мягкий красный
        x1, y1 = item.get("x1", 0), item.get("y1", 0)
        x2, y2 = item.get("x2", 0), item.get("y2", 0)

        # Переопределяем цвета для современного стиля
        if color == "red":
            color = "#E57373"
        elif color == "green":
            color = "#81C784"
        elif color == "yellow":
            color = "#FFD54F"
        elif color == "white":
            color = "#FFFFFF"

        try:
            if shape_type == "line":
                _draw_line_handdrawn(draw, x1, y1, x2, y2, color, width=3, opacity=230)

            elif shape_type == "dashed_line":
                _draw_dashed_line(draw, x1, y1, x2, y2, color, width=3, dash=15, gap=8, opacity=230)

            elif shape_type == "crop_frame":
                _draw_crop_frame(draw, result, x1, y1, x2, y2, color)

            elif shape_type == "grid_thirds":
                _draw_grid_thirds(draw, result, color)

            elif shape_type == "circle":
                rx, ry = x2, y2
                _draw_marker_circle(draw, x1, y1, rx, ry, "#FFB74D", width=4, opacity=230)

            elif shape_type == "frame":
                _draw_marker_arc(draw, x1, y1, x2, y2, "#FFB74D", width=4, opacity=230)

            elif shape_type == "arrow":
                _draw_arrow(draw, x1, y1, x2, y2, color, width=3, opacity=230)

        except Exception as e:
            print(f"Не удалось нарисовать {shape_type}: {e}")
            continue

    return result
