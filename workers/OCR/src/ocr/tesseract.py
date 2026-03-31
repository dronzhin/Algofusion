# workers/ocr/ocr/tesseract.py
"""
Tesseract OCR движок (обработка в памяти).
"""

from typing import List, Union
from PIL import Image, ImageEnhance
import pytesseract

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine

logger = setup_logger("workers.ocr.ocr.tesseract")


class TesseractEngine(OCREngine):
    """Tesseract OCR с обработкой в памяти."""

    name = "tesseract"

    def __init__(self, config: dict):
        super().__init__(config)
        lang_config = config.get("lang", "rus+eng")
        self.lang = lang_config if isinstance(lang_config, str) else "+".join(lang_config)

        self.oem = config.get("oem", 1)
        self.psm = config.get("psm", 11)
        self.preprocess = config.get("preprocess", False)

    def process(self, img: Image.Image) -> str:
        """Распознавание одного изображения в памяти."""
        logger.debug(f"🔤 Tesseract: {img.size}px, режим {img.mode}")

        # Конвертируем в RGB если нужно
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Предобработка если включена
        if self.preprocess:
            img = self._preprocess(img)

        # Конфигурация Tesseract
        config_str = f"--oem {self.oem} --psm {self.psm}"

        # 🔹 Распознавание (lang теперь строка!)
        text = pytesseract.image_to_string(
            img,
            lang=self.lang,
            config=config_str
        ).strip()

        logger.debug(f"✅ Tesseract: {len(text)} символов")
        return text

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """Пакетная обработка с логированием."""
        logger.info(f"🔤 Tesseract: обработка {len(images)} изображений")
        return super().process_batch(images)

    def _preprocess(self, img: Image.Image) -> Image.Image:
        """Базовая предобработка: контраст + бинаризация."""
        # Увеличение контраста
        img = ImageEnhance.Contrast(img).enhance(1.2)
        # Конвертация в оттенки серого
        img = img.convert("L")
        # Бинаризация
        img = img.point(lambda x: 255 if x > 128 else 0, mode="1")
        # Обратно в RGB для pytesseract
        return img.convert("RGB")