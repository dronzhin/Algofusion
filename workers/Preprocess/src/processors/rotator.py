# workers/Preprocess/src/processors/rotator.py
"""
Процессор: автоматический поворот изображения (в памяти).
Только для контейнера processor.
"""

import cv2
import numpy as np
from PIL import Image
from typing import List

from shared.utils.logger import setup_logger
from workers.Preprocess.src.processors.base import ImageProcessorStep

logger = setup_logger("workers.Preprocess.processors.rotator")


class Rotator(ImageProcessorStep):
    """Автоматический поворот изображений в памяти."""

    def __init__(
        self,
        angle_threshold: float = 0.5,
        scale: float = 1.0,
    ):
        super().__init__("rotator")
        self.angle_threshold = angle_threshold
        self.scale = scale

    def process(self, img: Image.Image) -> Image.Image:
        """Поворот одного изображения."""
        logger.debug(f"🔄 Поворот: {img.size}px")

        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        angle = self._detect_angle(cv_img)

        if abs(angle) < self.angle_threshold:
            return img

        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, self.scale)
        rotated = cv2.warpAffine(cv_img, rotation_matrix, (w, h))

        result_rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)

    def process_batch(self, images: List[Image.Image]) -> List[Image.Image]:
        """Пакетная обработка с логированием."""
        logger.info(f"🔄 Поворот {len(images)} изображений")
        return super().process_batch(images)

    def _detect_angle(self, image: np.ndarray) -> float:
        """Детекция угла поворота."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return 0.0

        max_contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(max_contour)
        angle = rect[-1]

        if angle > 45:
            angle = angle + 270

        return angle