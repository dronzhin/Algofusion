# workers/ocr/src/ocr/easyocr.py
"""
EasyOCR движок (обработка в памяти).
"""

from pathlib import Path
from typing import List
import numpy as np
from PIL import Image

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine

logger = setup_logger("workers.ocr.ocr.easyocr")


class EasyOCREngine(OCREngine):
    """EasyOCR с обработкой в памяти."""

    name = "easyocr"

    def __init__(self, config: dict):
        super().__init__(config)
        self.lang_list = config.get("lang", ["ru", "en"])
        self.gpu = config.get("gpu", False)
        self.min_score = config.get("min_score", 0.5)
        self._reader = None  # Ленивая инициализация

    def _get_reader(self):
        """Ленивая инициализация EasyOCR Reader."""
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(
                self.lang_list,
                gpu=self.gpu,
                verbose=False
            )
            logger.info(f"✅ EasyOCR инициализирован: языки={self.lang_list}")
        return self._reader

    def process(self, img: Image.Image) -> str:
        """Распознавание одного изображения в памяти."""
        logger.debug(f"🔤 EasyOCR: {img.size}px")

        # Конвертируем PIL → numpy array (BGR для EasyOCR)
        img_array = np.array(img.convert("RGB"))

        # Распознавание
        reader = self._get_reader()
        results = reader.readtext(
            img_array,
            detail=1,
            min_score=self.min_score,
            paragraph=False
        )

        # Извлекаем текст
        text_lines = [r[1] for r in results]
        text = "\n".join(text_lines)

        logger.debug(f"✅ EasyOCR: {len(text)} символов, {len(results)} детекций")
        return text

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """Пакетная обработка с логированием."""
        logger.info(f"🔤 EasyOCR: обработка {len(images)} изображений")
        return super().process_batch(images)