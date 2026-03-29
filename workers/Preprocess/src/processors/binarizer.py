# workers/Preprocess/src/processors/binarizer.py
"""
Процессор: бинаризация изображения.
Только для контейнера processor.
"""

import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

from shared.utils.logger import setup_logger
from workers.Preprocess.src.processors.base import ImageProcessorStep

logger = setup_logger("processor.processors.binarizer")


class Binarizer(ImageProcessorStep):
    """Бинаризация с пороговой обработкой и шумоподавлением."""

    def __init__(
            self,
            background_threshold: int = 128,
            binary_threshold: int = 128,
            median_iterations: int = 5,
            median_size: int = 3,
    ):
        super().__init__("binarizer")
        self.bg_threshold = background_threshold
        self.bin_threshold = binary_threshold
        self.median_iterations = median_iterations
        self.median_size = median_size

    def validate_input(self, input_path: Path) -> bool:
        if not input_path.exists():
            return False
        try:
            Image.open(input_path).verify()
            return True
        except:
            return False

    def process(self, input_path: Path, output_path: Path) -> Path:
        logger.debug(f"🔲 Бинаризация: {input_path.name}")

        img = Image.open(input_path).convert("L")
        arr = np.array(img)

        # Пороговая обработка фона
        arr = np.where(arr > self.bg_threshold, 255, arr)
        # Бинаризация
        arr = np.where(arr <= self.bin_threshold, 1, 255)

        img = Image.fromarray(arr.astype(np.uint8))

        # Медианная фильтрация
        for _ in range(self.median_iterations):
            img = img.filter(ImageFilter.MedianFilter(size=self.median_size))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG")

        logger.debug(f"✅ Бинаризация завершена: {output_path.name}")
        return output_path