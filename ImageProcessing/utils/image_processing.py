import cv2
import numpy as np
from PIL import Image
import io
import base64
import logging

logger = logging.getLogger(__name__)

def binary_convert(image_bytes: bytes, threshold: int) -> bytes:
    """
    Конвертирует изображение в бинарный формат (только черный и белый)

    Args:
        image_bytes: Байты исходного изображения
        threshold: Порог бинаризации (0-255)

    Returns:
        Байты бинарного изображения в формате PNG
    """
    try:
        # Загружаем изображение
        img = Image.open(io.BytesIO(image_bytes))

        # Конвертируем в grayscale если необходимо
        if img.mode != 'L':
            img = img.convert('L')

        # Применяем бинаризацию
        threshold = max(0, min(255, threshold))
        img_bw = img.point(lambda x: 255 if x > threshold else 0, mode='1')

        # Сохраняем в PNG
        output_buffer = io.BytesIO()
        img_bw.save(output_buffer, format="PNG")
        output_buffer.seek(0)

        return output_buffer.getvalue()

    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка бинаризации изображения: {safe_error}")
        raise ValueError(f"Ошибка бинаризации изображения: {safe_error}")


def find_longest_horizontal_line(image_bytes: bytes, min_line_length: int = 50, max_line_gap: int = 20) -> dict:
    """
    Находит самую длинную горизонтальную линию на изображении

    Args:
        image_bytes: Байты изображения
        min_line_length: Минимальная длина линии
        max_line_gap: Максимальный разрыв в линии

    Returns:
        Словарь с информацией о линии или None если линии не найдены
    """
    try:
        # Конвертируем байты в изображение OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Не удалось загрузить изображение")

        # Конвертируем в оттенки серого
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Применяем размытие для уменьшения шума
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Детектируем границы
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Находим линии с помощью преобразования Хафа
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap
        )

        if lines is None or len(lines) == 0:
            return None

        # Фильтруем горизонтальные линии и находим самую длинную
        horizontal_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

            # Вычисляем угол линии в градусах
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))

            # Нормализуем угол к диапазону [-90, 90]
            if angle < -90:
                angle += 180
            elif angle > 90:
                angle -= 180

            # Считаем линию горизонтальной, если угол близок к 0 или 180
            if abs(angle) < 15 or abs(abs(angle) - 180) < 15:
                horizontal_lines.append({
                    'coords': (x1, y1, x2, y2),
                    'length': length,
                    'angle': angle
                })

        if not horizontal_lines:
            return None

        # Находим самую длинную горизонтальную линию
        longest_line = max(horizontal_lines, key=lambda x: x['length'])
        return {
            'start': (longest_line['coords'][0], longest_line['coords'][1]),
            'end': (longest_line['coords'][2], longest_line['coords'][3]),
            'length': longest_line['length'],
            'angle': longest_line['angle']
        }

    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка детекции линий: {safe_error}")
        raise ValueError(f"Ошибка детекции линий: {safe_error}")


def rotate_image(image_bytes: bytes, angle: float) -> bytes:
    """
    Поворачивает изображение на заданный угол

    Args:
        image_bytes: Байты исходного изображения
        angle: Угол поворота в градусах

    Returns:
        Байты повернутого изображения в формате PNG
    """
    try:
        # Конвертируем байты в изображение OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Не удалось загрузить изображение для поворота")

        # Поворачиваем изображение
        height, width = img.shape[:2]
        center = (width // 2, height // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, rotation_matrix, (width, height), flags=cv2.INTER_LINEAR)

        # Конвертируем в PNG
        is_success, buffer = cv2.imencode(".png", rotated)
        if not is_success:
            raise ValueError("Ошибка конвертации повернутого изображения")

        return buffer.tobytes()

    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка поворота изображения: {safe_error}")
        raise ValueError(f"Ошибка поворота изображения: {safe_error}")


def apply_morphology(image_bytes: bytes) -> bytes:
    """
    Применяет морфологические операции к бинарному изображению

    Args:
        image_bytes: Байты бинарного изображения

    Returns:
        Байты обработанного изображения
    """
    try:
        # Конвертируем байты в изображение OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

        if img is None:
            raise ValueError("Не удалось загрузить изображение для морфологии")

        # Применяем морфологическое закрытие для соединения линий
        kernel = np.ones((3, 3), np.uint8)
        closed = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)

        # Применяем морфологическое открытие для удаления шума
        cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)

        # Конвертируем обратно в байты
        is_success, buffer = cv2.imencode(".png", cleaned)
        if not is_success:
            raise ValueError("Ошибка конвертации после морфологии")

        return buffer.tobytes()

    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка морфологической обработки: {safe_error}")
        raise ValueError(f"Ошибка морфологической обработки: {safe_error}")