# workers/ocr/src/ocr/easyocr.py
"""EasyOCR движок."""

from pathlib import Path
from typing import Any, Dict, Optional
import time

from src.ocr.base import BaseOCREngine, OCRResult
from src.ocr.registry import OCREngineRegistry
from src.logger import get_logger

logger = get_logger(__name__)


@OCREngineRegistry.register
class EasyOCREngine(BaseOCREngine):
    """OCR движок на основе EasyOCR."""

    name = "easyocr"
    description = "EasyOCR Engine (точный для рукописного текста, медленнее)"
    version = "1.0.0"

    supported_languages = {"ru", "en", "de", "fr", "es", "it", "zh", "ja", "ko"}
    supported_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "lang": ["ru", "en"],
            "gpu": False,
            "detail": 1,
            "min_score": 0.5,
            "paragraph": False
        }

    def process(self, input_path: Path, output_path: Path = None) -> OCRResult:
        start_time = time.time()

        try:
            self.validate_input(input_path)

            logger.debug(f"EasyOCR обработка: {input_path}")

            import easyocr
            reader = easyocr.Reader(
                self.config["lang"],
                gpu=self.config.get("gpu", False),
                verbose=False
            )

            results = reader.readtext(
                str(input_path),
                detail=self.config.get("detail", 1),
                min_score=self.config.get("min_score", 0.5),
                paragraph=self.config.get("paragraph", False)
            )

            if self.config.get("detail", 1) == 1:
                text = "\n".join([r[1] for r in results])
                confidences = [r[2] for r in results]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            else:
                text = "\n".join([r for r in results])
                avg_confidence = 0.0

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(text, encoding="utf-8")

            duration = time.time() - start_time

            return OCRResult(
                success=True,
                text=text,
                confidence=avg_confidence,
                duration=duration,
                engine=self.name,
                metadata={
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "detections": len(results),
                    "avg_confidence": avg_confidence
                }
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"EasyOCR ошибка: {e}")
            return OCRResult(
                success=False,
                text="",
                duration=duration,
                engine=self.name,
                error=str(e)
            )