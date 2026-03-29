# workers/Preprocess/src/processors/rotator.py
"""
Процессор: автоматический поворот изображения.
Только для контейнера processor.
"""

import cv2
import numpy as np
from pathlib import Path

from shared.utils.logger import setup_logger
from workers.Preprocess.src.processors.base import ImageProcessorStep

logger = setup_logger("processor.processors.rotator")


class Rotator(ImageProcessorStep):
    """Автоматический поворот на основе детекции контуров."""

    def __init__(
            self,
            angle_threshold: float = 0.5,
            scale: float = 1.0,
            use_otsu: bool = True,
    ):
        super().__init__("rotator")
        self.angle_threshold = angle_threshold
        self.scale = scale
        self.use_otsu = use_otsu

    def validate_input(self, input_path: Path) -> bool:
        if not input_path.exists():
            return False
        return cv2.imread(str(input_path)) is not None

    def _detect_angle(self, image: np.ndarray) -> float:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self.use_otsu:
            _, thresh = cv2.threshold(
                gray, 0, 255,
                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
        else:
            _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return 0.0

        max_contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(max_contour)
        angle = rect[-1]

        if angle > 45:
            angle = angle + 270

        return angle

    def process(self, input_path: Path, output_path: Path) -> Path:
        logger.debug(f"🔄 Поворот: {input_path.name}")

        image = cv2.imread(str(input_path))
        if image is None:
            logger.error(f"Не удалось прочитать: {input_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if input_path != output_path:
                input_path.rename(output_path)
            return output_path

        angle = self._detect_angle(image)

        if abs(angle) < self.angle_threshold:
            logger.debug(f"⏭️ Угол {angle:.2f}° < порога")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), image)
            return output_path

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, self.scale)
        rotated = cv2.warpAffine(image, rotation_matrix, (w, h))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), rotated)

        logger.info(f"✅ Поворот: {input_path.name} → {angle:.2f}°")
        return output_path