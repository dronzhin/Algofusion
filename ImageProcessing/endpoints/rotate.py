# endpoints/rotate.py
"""
Эндпоинт для поворота изображений
"""
from fastapi import UploadFile, HTTPException
from typing import Dict, Union, Optional
import base64
import cv2
import numpy as np
from utils import get_logger
import traceback

logger = get_logger(__name__)


async def rotate_image_endpoint(
        file: UploadFile,
        min_line_length: int = 50,
        max_line_gap: int = 20,
        use_morphology: bool = False,
        debug_mode: bool = False
) -> Dict[str, Union[str, float, dict, bool, Optional[str]]]:
    """
    Обработчик эндпоинта /rotate с безопасной инициализацией переменных
    """
    try:
        # Читаем содержимое файла
        contents = await file.read()

        # Проверяем, что файл не пустой
        if len(contents) == 0:
            raise ValueError("Пустой файл")

        # Конвертируем байты в изображение OpenCV
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise ValueError("Не удалось загрузить изображение. Проверьте формат файла.")

        logger.debug("=" * 50)
        logger.debug(f"DEBUG: Начало обработки файла: {file.filename}")
        logger.debug(f"DEBUG: Размер изображения: {img.shape}")
        logger.debug(f"DEBUG: Тип изображения: {img.dtype}")
        logger.debug(
            f"DEBUG: Настройки: min_line_length={min_line_length}, max_line_gap={max_line_gap}, use_morphology={use_morphology}")
        logger.debug("=" * 50)

        # ИНИЦИАЛИЗИРУЕМ ПЕРЕМЕННЫЕ ЗАРАНЕЕ для избежания ошибок
        horizontal_lines = []
        all_lines_debug = []
        rotation_angle = 0.0
        line_info = None

        # Сохраняем оригинальное изображение для поворота
        original_img = img.copy()

        # Применяем морфологию если нужно
        if use_morphology:
            logger.debug("DEBUG: Применение морфологических операций")
            if len(img.shape) == 3:  # Если цветное
                gray_for_morph = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray_for_morph = img.copy()

            kernel = np.ones((3, 3), np.uint8)
            closed = cv2.morphologyEx(gray_for_morph, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)

            if len(img.shape) == 3:
                img = cleaned
            else:
                img = cleaned

        # Конвертируем в оттенки серого если цветное
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            logger.debug("DEBUG: Конвертировано в grayscale")
        else:
            gray = img.copy()

        # Применяем размытие
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        logger.debug(f"DEBUG: Применено размытие")

        # Детектируем границы
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
        edge_count = np.sum(edges > 0)
        logger.debug(f"DEBUG: Детектировано границ: {edge_count} пикселей")

        # Находим линии с помощью преобразования Хафа
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap
        )

        line_count = len(lines) if lines is not None else 0
        logger.debug(f"DEBUG: Найдено линий: {line_count}")

        if lines is not None and line_count > 0:
            for i, line in enumerate(lines):
                x1, y1, x2, y2 = line[0]
                # ИСПРАВЛЕНО: правильное вычисление длины линии
                length = np.sqrt((x2 - x1) ** 2 +  (y2 - y1) **2)

                # Правильное вычисление угла
                dy = -(y2 - y1)  # Инвертируем ось Y
                dx = x2 - x1
                angle = np.degrees(np.arctan2(dy, dx))

                # Нормализуем угол
                if angle < -90:
                    angle += 180
                elif angle > 90:
                    angle -= 180

                # Отладочная информация
                all_lines_debug.append({
                    'line_index': i,
                    'coords': (int(x1), int(y1), int(x2), int(y2)),
                    'length': float(length),
                    'raw_angle': float(np.degrees(np.arctan2(y2 - y1, x2 - x1))),
                    'corrected_angle': float(angle),
                    'dx': dx,
                    'dy': dy
                })

                logger.debug(
                    f"DEBUG: Линия {i}: coords=({x1},{y1})-({x2},{y2}), length={length:.1f}, corrected_angle={angle:.2f}°")

                # Считаем линию горизонтальной
                is_horizontal = False
                if abs(angle) < 20:  # Порог 20 градусов
                    is_horizontal = True
                elif abs(abs(angle) - 180) < 20:
                    is_horizontal = True

                if is_horizontal:
                    horizontal_lines.append({
                        'coords': (int(x1), int(y1), int(x2), int(y2)),
                        'length': float(length),
                        'angle': float(angle)
                    })
                    logger.debug(f"  ✓ Линия {i} считается горизонтальной (angle={angle:.2f}°)")
                else:
                    logger.debug(f"  ✗ Линия {i} НЕ горизонтальная (angle={angle:.2f}°)")

            logger.debug(f"DEBUG: Найдено горизонтальных линий: {len(horizontal_lines)}")

            if horizontal_lines:
                longest_line = max(horizontal_lines, key=lambda x: x['length'])
                x1, y1, x2, y2 = longest_line['coords']
                line_angle = longest_line['angle']

                # Правильная логика поворота
                rotation_angle = -line_angle

                line_info = {
                    'start': (x1, y1),
                    'end': (x2, y2),
                    'length': longest_line['length'],
                    'detected_angle': line_angle,
                    'rotation_angle': rotation_angle
                }

                logger.debug("=" * 50)
                logger.debug("DEBUG: ВЫБРАНА ЛИНИЯ ДЛЯ ПОВОРОТА")
                logger.debug(f"Координаты: ({x1}, {y1}) - ({x2}, {y2})")
                logger.debug(f"Длина: {longest_line['length']:.1f} пикселей")
                logger.debug(f"Угол линии: {line_angle:.2f}°")
                logger.debug(f"Угол поворота: {rotation_angle:.2f}°")
                logger.debug("=" * 50)
            else:
                logger.debug("DEBUG: НЕТ горизонтальных линий, поворот не требуется")
                # Используем самую длинную линию как запасной вариант
                if lines is not None and len(lines) > 0:
                    all_lines = []
                    for line in lines:
                        x1, y1, x2, y2 = line[0]
                        # ИСПРАВЛЕНО: правильное вычисление длины (второе место)
                        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1)**2)
                        all_lines.append({
                            'coords': (int(x1), int(y1), int(x2), int(y2)),
                            'length': float(length)
                        })

                    longest_any_line = max(all_lines, key=lambda x: x['length'])
                    x1, y1, x2, y2 = longest_any_line['coords']

                    # Вычисляем угол для самой длинной линии
                    dy = -(y2 - y1)
                    dx = x2 - x1
                    angle = np.degrees(np.arctan2(dy, dx))

                    if angle < -90:
                        angle += 180
                    elif angle > 90:
                        angle -= 180

                    rotation_angle = -angle
                    line_info = {
                        'start': (x1, y1),
                        'end': (x2, y2),
                        'length': longest_any_line['length'],
                        'detected_angle': angle,
                        'rotation_angle': rotation_angle,
                        'warning': 'Использована НЕ горизонтальная линия'
                    }
                    logger.debug(
                        f"DEBUG: Использована самая длинная линия для поворота: angle={angle:.2f}°, rotation_angle={rotation_angle:.2f}°")
        else:
            logger.debug("DEBUG: Не найдено линий для анализа")

        logger.debug(f"DEBUG: Применяем поворот на угол: {rotation_angle:.2f}°")

        # Поворачиваем оригинальное изображение
        height, width = original_img.shape[:2]
        center = (width // 2, height // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)

        rotated = cv2.warpAffine(original_img, rotation_matrix, (width, height),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(255, 255, 255))

        logger.debug("DEBUG: Поворот применен успешно")

        # Конвертируем в PNG
        is_success, buffer = cv2.imencode(".png", rotated)
        if not is_success or buffer.size == 0:
            raise ValueError("Ошибка конвертации изображения в PNG")

        logger.debug(f"DEBUG: Размер буфера PNG: {buffer.size} байт")

        # Кодируем в base64
        rotated_b64 = base64.b64encode(buffer).decode('utf-8')

        # Формируем ответ
        return {
            "rotated_image_base64": rotated_b64,
            "rotation_angle": rotation_angle,
            "line_info": line_info,
            "success": True,
            "debug_info": {
                "total_lines_found": line_count,
                "horizontal_lines_found": len(horizontal_lines),
                "edge_pixel_count": int(edge_count),
                "image_shape": list(original_img.shape),
                "applied_rotation_angle": rotation_angle
            }
        }

    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        logger.error(f"Трейсбек:\n{traceback.format_exc()}")

        # Очищаем ошибку от непечатаемых символов
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        safe_details = traceback.format_exc().encode('utf-8', 'ignore').decode('utf-8')[:500]

        return {
            "rotated_image_base64": None,
            "rotation_angle": 0.0,
            "line_info": None,
            "success": False,
            "error": safe_error,
            "error_details": safe_details
        }