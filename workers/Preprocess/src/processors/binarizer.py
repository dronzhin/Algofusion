# workers/Preprocess/src/processors/binarizer.py
"""
Процессор: бинаризация изображения (в памяти).
Только для контейнера processor.
"""

import numpy as np
from PIL import Image, ImageFilter

from shared.utils.logger import setup_logger
from workers.Preprocess.src.processors.base import ImageProcessorStep

logger = setup_logger("workers.Preprocess.processors.binarizer")


class Binarizer(ImageProcessorStep):
    """Бинаризация изображений в памяти."""

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

    def process(self, img: Image.Image) -> Image.Image:
        """Бинаризация одного изображения."""
        logger.debug(f"🔲 Бинаризация: {img.size}px")

        if img.mode != "L":
            img = img.convert("L")

        arr = np.array(img)
        arr = np.where(arr > self.bg_threshold, 255, arr)
        arr = np.where(arr <= self.bin_threshold, 1, 255)

        img = Image.fromarray(arr.astype(np.uint8))

        for _ in range(self.median_iterations):
            img = img.filter(ImageFilter.MedianFilter(size=self.median_size))

        return img