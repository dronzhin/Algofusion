import cv2
import numpy as np
from PIL import Image
import base64
from io import BytesIO
from typing import Dict, Any, List, Optional
from config import Config


class ImageService:
    """
    Сервис для обработки изображений
    Содержит бизнес-логику без привязки к Streamlit UI
    """

    @staticmethod
    def detect_horizontal_lines(image_bytes: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Детекция горизонтальных линий на изображении
        """
        try:
            # Загрузка изображения
            img = Image.open(BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img_array = np.array(img)

            # Конвертация в grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Применение морфологических операций
            if params.get("use_morphology", True):
                kernel = np.ones((3, 3), np.uint8)
                gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

            # Применение Canny edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            # Настройки HoughLinesP
            min_line_length = params.get("min_line_length", 50)
            max_line_gap = params.get("max_line_gap", 20)

            # Детекция линий
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=100,
                minLineLength=min_line_length,
                maxLineGap=max_line_gap
            )

            if lines is None:
                return {
                    "success": False,
                    "error": "Горизонтальные линии не найдены",
                    "lines": []
                }

            # Фильтрация горизонтальных линий
            horizontal_lines = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                angle_abs = abs(angle)

                # Считаем линию горизонтальной, если угол близок к 0 или 180 градусам
                if angle_abs < 10 or angle_abs > 170:
                    length = np.sqrt((x2 - x1) ** 2 +  (y2 - y1) ** 2)
                    horizontal_lines.append({
                        "coords": (x1, y1, x2, y2),
                        "angle": angle,
                        "length": length
                    })

            if not horizontal_lines:
                return {
                    "success": False,
                    "error": "Горизонтальные линии не найдены",
                    "lines": []
                }

            # Находим самую длинную горизонтальную линию
            longest_line = max(horizontal_lines, key=lambda x: x["length"])

            return {
                "success": True,
                "line_info": {
                    "start": (longest_line["coords"][0], longest_line["coords"][1]),
                    "end": (longest_line["coords"][2], longest_line["coords"][3]),
                    "detected_angle": longest_line["angle"],
                    "length": longest_line["length"]
                },
                "all_lines": horizontal_lines
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при детекции линий: {str(e)}",
                "lines": []
            }

    @staticmethod
    def rotate_image(image_bytes: bytes, angle: float) -> bytes:
        """
        Поворот изображения на заданный угол
        """
        try:
            img = Image.open(BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Поворот изображения
            rotated_img = img.rotate(-angle, expand=True, resample=Image.BICUBIC)

            # Сохранение в байты
            img_byte_arr = BytesIO()
            rotated_img.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()

        except Exception as e:
            raise Exception(f"Ошибка при повороте изображения: {str(e)}") from e

    @staticmethod
    def convert_to_binary(image_bytes: bytes, threshold: int) -> bytes:
        """
        Конвертация изображения в бинарный формат
        """
        try:
            img = Image.open(BytesIO(image_bytes))

            # Конвертация в grayscale если нужно
            if img.mode != 'L':
                img = img.convert('L')

            # Применение порога
            binary_img = img.point(lambda p: 255 if p > threshold else 0, '1')

            # Сохранение в байты
            img_byte_arr = BytesIO()
            binary_img.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()

        except Exception as e:
            raise Exception(f"Ошибка при бинаризации: {str(e)}") from e

    @staticmethod
    def process_image_for_rotation(image_bytes: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полный процесс выравнивания изображения
        """
        # Детекция линий
        detection_result = ImageService.detect_horizontal_lines(image_bytes, params)

        if not detection_result["success"]:
            # Если линии не найдены, возвращаем исходное изображение
            return {
                "success": True,
                "rotated_image": image_bytes,
                "rotation_angle": 0.0,
                "line_info": None,
                "message": "Горизонтальные линии не найдены, изображение не изменено"
            }

        line_info = detection_result["line_info"]
        detected_angle = line_info["detected_angle"]

        # Определяем угол поворота для выравнивания
        if abs(detected_angle) < 10:
            rotation_angle = -detected_angle
        elif detected_angle > 170:
            rotation_angle = -(detected_angle - 180)
        elif detected_angle < -170:
            rotation_angle = -(detected_angle + 180)
        else:
            rotation_angle = -detected_angle

        # Поворачиваем изображение
        rotated_bytes = ImageService.rotate_image(image_bytes, rotation_angle)

        return {
            "success": True,
            "rotated_image": rotated_bytes,
            "rotation_angle": rotation_angle,
            "line_info": line_info
        }