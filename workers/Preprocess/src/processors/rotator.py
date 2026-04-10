# workers/Preprocess/src/processors/rotator.py
"""
Процессор: автоматический поворот изображения (в памяти).
Только для контейнера processor.

🔹 УЛУЧШЕНИЯ:
- Детекция угла по нескольким контурам, а не только по наибольшему
- Отсев подозрительных углов (>30°) с повторной проверкой
- Фоллбэк на проекционный анализ, если контуры ненадёжны
"""

import cv2
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple

from shared.utils.logger import setup_logger
from workers.Preprocess.src.processors.base import ImageProcessorStep

logger = setup_logger("workers.Preprocess.processors.rotator")


class Rotator(ImageProcessorStep):
    """Автоматический поворот изображений в памяти."""

    def __init__(
            self,
            angle_threshold: float = 0.5,  # Минимальный угол для поворота
            max_reliable_angle: float = 30.0,  # Максимальный "надёжный" угол
            scale: float = 1.0,
    ):
        super().__init__("rotator")
        self.angle_threshold = angle_threshold
        self.max_reliable_angle = max_reliable_angle
        self.scale = scale

    def process(self, img: Image.Image) -> Image.Image:
        """Поворот одного изображения."""
        logger.debug(f"🔄 Обработка изображения: {img.size}px")

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        angle = self._detect_angle_robust(cv_img)

        if angle is None or abs(angle) < self.angle_threshold:
            logger.debug(f"✅ Поворот не требуется (угол: {angle})")
            return img

        logger.info(f"🔄 Поворот на {angle:.2f}°")

        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, self.scale)

        # Поворот с заполнением фона белым цветом (для документов)
        rotated = cv2.warpAffine(
            cv_img,
            rotation_matrix,
            (w, h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)  # Белый фон
        )

        result_rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)

    def process_batch(self, images: List[Image.Image]) -> List[Image.Image]:
        """Пакетная обработка с логированием."""
        logger.info(f"🔄 Поворот {len(images)} изображений")
        return super().process_batch(images)

    def _detect_angle_robust(self, image: np.ndarray) -> Optional[float]:
        """
        Надёжная детекция угла поворота.

        Алгоритм:
        1. Пробуем детектировать по крупным контурам (текстовые блоки)
        2. Если угол подозрительный (>30°) — пробуем альтернативные контуры
        3. Если не удалось — фоллбэк на проекционный анализ
        4. Если всё ещё ненадёжно — возвращаем None (не поворачивать)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 🔹 Предобработка: бинаризация + морфология для улучшения контуров
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 🔹 Находим контуры
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            logger.debug("⚠️ Не найдено контуров, пробуем проекционный анализ")
            return self._detect_angle_by_projection(gray)

        # 🔹 Фильтруем контуры: оставляем только достаточно крупные (текстовые блоки)
        min_area = image.shape[0] * image.shape[1] * 0.01  # Минимум 1% от изображения
        valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area]

        if not valid_contours:
            logger.debug("⚠️ Нет крупных контуров, пробуем проекционный анализ")
            return self._detect_angle_by_projection(gray)

        # 🔹 Сортируем по площади (убывание)
        valid_contours.sort(key=cv2.contourArea, reverse=True)

        # 🔹 Пробуем детектировать угол по нескольким крупным контурам
        angles = []
        for i, contour in enumerate(valid_contours[:5]):  # Проверяем топ-5
            angle = self._get_angle_from_contour(contour, image.shape)
            if angle is not None:
                angles.append(angle)

                # 🔹 Если угол надёжный (<=30°) — сразу возвращаем
                if abs(angle) <= self.max_reliable_angle:
                    logger.debug(f"✅ Надёжный угол {angle:.2f}° найден по контуру #{i + 1}")
                    return angle

        # 🔹 Если все углы подозрительные (>30°) — выбираем наименьший по модулю
        if angles:
            best_angle = min(angles, key=abs)
            logger.warning(f"⚠️ Все углы подозрительные, выбран наименьший: {best_angle:.2f}°")
            return best_angle if abs(best_angle) <= 45 else None

        # 🔹 Фоллбэк на проекционный анализ
        logger.debug("⚠️ Не удалось определить угол по контурам, пробуем проекции")
        return self._detect_angle_by_projection(gray)

    def _get_angle_from_contour(self, contour: np.ndarray, image_shape: Tuple) -> Optional[float]:
        """
        Получает угол поворота из контура с корректной нормализацией.

        Returns:
            float: Угол в градусах или None, если контур ненадёжный
        """
        # Проверяем, что контур достаточно "вытянутый" (не круг)
        rect = cv2.minAreaRect(contour)
        (cx, cy), (width, height), angle = rect

        # Если ширина и высота почти равны — контур неинформативен
        if width > 0 and height > 0:
            aspect_ratio = max(width, height) / min(width, height)
            if aspect_ratio < 1.5:  # Слишком "квадратный"
                return None

        # 🔹 Нормализация угла: cv2 возвращает [-90, 0), нам нужно [-180, 180]
        if width < height:
            angle = 90 + angle
        else:
            angle = angle

        # Приводим к диапазону [-90, 90]
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        return angle

    def _detect_angle_by_projection(self, gray: np.ndarray) -> Optional[float]:
        """
        Детекция угла по проекционному анализу (фоллбэк-метод).

        Идея: текст в строках создаёт чёткие горизонтальные "пики" в проекции.
        При наклоне документа пики смещаются — по этому смещению вычисляем угол.
        """
        h, w = gray.shape

        # 🔹 Пробуем несколько углов в диапазоне [-15, 15] с шагом 1°
        best_score = -1
        best_angle = 0.0

        for test_angle in range(-15, 16):
            # Поворачиваем изображение на тестовый угол
            M = cv2.getRotationMatrix2D((w // 2, h // 2), test_angle, 1.0)
            rotated = cv2.warpAffine(gray, M, (w, h),
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=255)

            # 🔹 Горизонтальная проекция (сумма по строкам)
            projection = np.sum(rotated < 128, axis=1)  # Считаем тёмные пиксели

            # 🔹 Оценка: чем чётче "пики" (строки текста), тем лучше
            # Вычисляем дисперсию проекции — у выровненного текста она выше
            score = np.var(projection)

            if score > best_score:
                best_score = score
                best_angle = test_angle

        # 🔹 Возвращаем угол, только если он значительно лучше остальных
        if best_score > 1000:  # Порог "уверенности"
            logger.debug(f"✅ Проекционный анализ: угол {best_angle}° (score={best_score:.0f})")
            return float(best_angle)
        else:
            logger.debug(f"⚠️ Проекционный анализ ненадёжен (score={best_score:.0f})")
            return None

    def _is_text_like_contour(self, contour: np.ndarray, image_shape: Tuple) -> bool:
        """
        Эвристика: определяет, похож ли контур на текстовый блок.

        Текстовые блоки обычно:
        - Вытянуты горизонтально (ширина > высоты)
        - Имеют умеренный aspect ratio (не слишком тонкие)
        """
        rect = cv2.minAreaRect(contour)
        (cx, cy), (width, height), _ = rect

        if width <= 0 or height <= 0:
            return False

        aspect_ratio = width / height

        # Текстовый блок: ширина в 2-20 раз больше высоты
        return 2.0 <= aspect_ratio <= 20.0 and width > image_shape[1] * 0.1