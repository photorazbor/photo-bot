"""
Работа с изображениями: скачивание, сжатие и рисование подсказок поверх фото
"""
import io
import math
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


def _draw_dashed_line(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=4, dash=10, gap=5):
    """Рисует пунктирную линию от (x1,y1) до (x2,y2)."""
    total_length = math.hypot(x2 - x1, y2 - y1)
    if total_length == 0:
        return
    dx = (x2 - x1) / total_length
    dy = (y2 - y1) / total_length

    distance = 0
    while distance < total_length:
        start_x = x1 + dx * distance
        start_y = y1 + dy * distance
        end_distance = min(distance + dash, total_length)
        end_x = x1 + dx * end_distance
        end_y = y1 + dy * end_distance
        draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)
        distance += dash + gap


def _draw_arrow(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width=4, head_size=15):
    """Рисует стрелку от (x1,y1) к (x2,y2) с треугольным наконечником."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

    angle = math.atan2(y2 - y1, x2 - x1)
    left_angle = angle + math.radians(150)
    right_angle = angle - math.radians(150)

    left_point = (x2 + head_size * math.cos(left_angle), y2 + head_size * math.sin(left_angle))
    right_point = (x2 + head_size * math.cos(right_angle), y2 + head_size * math.sin(right_angle))

    draw.polygon([(x2, y2), left_point, right_point], fill=color)


def _draw_crop_frame(draw: ImageDraw.ImageDraw, image: Image.Image, x1, y1, x2, y2, color="yellow"):
    """Рисует жёлтую пунктирную рамку кадрирования и затемняет область за ней."""
    width, height = image.size

    # Затемняем область за рамкой
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    if y1 > 0:
        overlay_draw.rectangle([(0, 0), (width, y1)], fill=(0, 0, 0, 120))
    if y2 < height:
        overlay_draw.rectangle([(0, y2), (width, height)], fill=(0, 0, 0, 120))
    if x1 > 0:
        overlay_draw.rectangle([(0, y1), (x1, y2)], fill=(0, 0, 0, 120))
    if x2 < width:
        overlay_draw.rectangle([(x2, y1), (width, y2)], fill=(0, 0, 0, 120))

    image_rgba = image.convert("RGBA")
    image_rgba = Image.alpha_composite(image_rgba, overlay)
    image_rgba = image_rgba.convert("RGB")
    image.paste(image_rgba)

    # Жёлтая пунктирная рамка
    _draw_dashed_line(draw, x1, y1, x2, y1, color, width=4)
    _draw_dashed_line(draw, x1, y2, x2, y2, color, width=4)
    _draw_dashed_line(draw, x1, y1, x1, y2, color, width=4)
    _draw_dashed_line(draw, x2, y1, x2, y2, color, width=4)


def _draw_grid_thirds(draw: ImageDraw.ImageDraw, image: Image.Image, color="white"):
    """Рисует сетку правила третей: ТОНКИЕ полупрозрачные пунктирные линии."""
    width, height = image.size
    third_h = height // 3
    third_w = width // 3

    grid_color = (255, 255, 255, 77)

    grid_overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_overlay)

    _draw_dashed_line(grid_draw, 0, third_h, width, third_h, grid_color, width=1)
    _draw_dashed_line(grid_draw, 0, third_h * 2, width, third_h * 2, grid_color, width=1)
    _draw_dashed_line(grid_draw, third_w, 0, third_w, height, grid_color, width=1)
    _draw_dashed_line(grid_draw, third_w * 2, 0, third_w * 2, height, grid_color, width=1)

    image_rgba = image.convert("RGBA")
    image_rgba = Image.alpha_composite(image_rgba, grid_overlay)
    image_rgba = image_rgba.convert("RGB")
    image.paste(image_rgba)


def draw_hints(image: Image.Image, drawings: list) -> Image.Image:
    """
    Рисует поверх фото список подсказок (линии, круги, рамки, стрелки),
    полученных от ИИ. Не изменяет исходный объект — возвращает копию.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)

    for item in drawings:
        shape_type = item.get("type")
        color = item.get("color", "red")
        x1, y1 = item.get("x1", 0), item.get("y1", 0)
        x2, y2 = item.get("x2", 0), item.get("y2", 0)

        try:
            if shape_type == "line":
                draw.line([(x1, y1), (x2, y2)], fill=color, width=4)

            elif shape_type == "dashed_line":
                _draw_dashed_line(draw, x1, y1, x2, y2, color)

            elif shape_type == "crop_frame":
                _draw_crop_frame(draw, result, x1, y1, x2, y2, "yellow")

            elif shape_type == "grid_thirds":
                _draw_grid_thirds(draw, result, color)

            elif shape_type == "circle":
                rx, ry = x2, y2
                draw.ellipse(
                    [(x1 - rx, y1 - ry), (x1 + rx, y1 + ry)],
                    outline=color, width=4,
                )

            elif shape_type == "frame":
                draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=4)

            elif shape_type == "arrow":
                _draw_arrow(draw, x1, y1, x2, y2, color)

        except Exception as e:
            print(f"Не удалось нарисовать {shape_type}: {e}")
            continue

    return result