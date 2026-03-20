# workers/ocr/src/ocr/tesseract.py
"""Tesseract OCR движок."""

from pathlib import Path
from typing import Any, Dict, Optional
import time

import numpy as np
from PIL import Image
import pytesseract

from src.ocr.base import BaseOCREngine, OCRResult
from src.ocr.registry import OCREngineRegistry
from src.logger import get_logger

logger = get_logger(__name__)


@OCREngineRegistry.register
class TesseractEngine(BaseOCREngine):
    """OCR движок на основе Tesseract."""

    name = "tesseract"
    description = "Tesseract OCR Engine (быстрый, точный для печатного текста)"
    version = "1.0.0"

    supported_languages = {"rus", "eng", "deu", "fra", "spa", "ita"}
    supported_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".pdf"}

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "lang": "rus+eng",
            "oem": 1,
            "psm": 1,
            "preprocess": False,
            "dpi": 300
        }

    def process(self, input_path: Path, output_path: Path = None) -> OCRResult:
        start_time = time.time()

        try:
            self.validate_input(input_path)

            if not self.validate_language(self.config["lang"]):
                raise ValueError(f"Язык {self.config['lang']} не поддерживается")

            logger.debug(f"Tesseract обработка: {input_path}")

            if input_path.suffix.lower() == ".pdf":
                text = self._process_pdf(input_path)
            else:
                text = self._process_image(input_path)

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(text, encoding="utf-8")

            duration = time.time() - start_time

            return OCRResult(
                success=True,
                text=text,
                confidence=0.9,
                duration=duration,
                engine=self.name,
                metadata={
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "lines": len(text.splitlines())
                }
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tesseract ошибка: {e}")
            return OCRResult(
                success=False,
                text="",
                duration=duration,
                engine=self.name,
                error=str(e)
            )

    def _process_image(self, input_path: Path) -> str:
        """Обработка изображения."""
        img = np.array(Image.open(input_path).convert("RGB"))

        if self.config.get("preprocess", False):
            img = self._preprocess_image(img)

        config_str = f"--oem {self.config['oem']} --psm {self.config['psm']}"
        text = pytesseract.image_to_string(
            img,
            lang=self.config["lang"],
            config=config_str
        ).strip()

        return text

    def _process_pdf(self, input_path: Path) -> str:
        """Обработка PDF."""
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(input_path, dpi=self.config.get("dpi", 300))

            texts = []
            for img in images:
                img_array = np.array(img.convert("RGB"))
                config_str = f"--oem {self.config['oem']} --psm {self.config['psm']}"
                text = pytesseract.image_to_string(
                    img_array,
                    lang=self.config["lang"],
                    config=config_str
                )
                texts.append(text)

            return "\n\n".join(texts)

        except ImportError:
            raise ImportError("pdf2image не установлен. pip install pdf2image")

    def _preprocess_image(self, img: np.ndarray) -> np.ndarray:
        """Предобработка изображения."""
        from PIL import ImageEnhance

        pil_img = Image.fromarray(img)
        pil_img = ImageEnhance.Contrast(pil_img).enhance(1.2)
        img_gray = pil_img.convert("L")
        img_bw = img_gray.point(lambda x: 255 if x > 128 else 0, mode="1")
        return np.array(img_bw.convert("RGB"))