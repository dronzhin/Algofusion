# workers/ocr/src/ocr/suraya.py
"""Surya OCR движок."""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
from PIL import Image
import surya
from surya.detection import DetectionPredictor
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor

from src.ocr.base import BaseOCREngine, OCRResult
from src.ocr.registry import OCREngineRegistry

logger = logging.getLogger(__name__)


@OCREngineRegistry.register
class SuryaEngine(BaseOCREngine):
    """OCR движок на основе Surya."""

    name = "surya"
    description = "Surya OCR Engine (подходит для сложных документов и ROI OCR)"
    version = getattr(surya, "__version__", "unknown")

    supported_languages = {"rus", "eng", "deu", "fra", "spa", "ita"}
    supported_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp", ".pdf"}

    _foundation: Optional[FoundationPredictor] = None
    _detector: Optional[DetectionPredictor] = None
    _recognizer: Optional[RecognitionPredictor] = None

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "lang": "rus+eng",
            "dpi": 200,
            "return_boxes": True,
        }

    @classmethod
    def _ensure_models(cls) -> Tuple[FoundationPredictor, DetectionPredictor, RecognitionPredictor]:
        if cls._foundation is None:
            cls._foundation = FoundationPredictor()
        if cls._detector is None:
            cls._detector = DetectionPredictor()
        if cls._recognizer is None:
            cls._recognizer = RecognitionPredictor(cls._foundation)
        return cls._foundation, cls._detector, cls._recognizer

    def process(self, input_path: Path, output_path: Path = None) -> OCRResult:
        start_time = time.time()

        try:
            self.validate_input(input_path)

            if not self.validate_language(self.config["lang"]):
                raise ValueError(f"Язык {self.config['lang']} не поддерживается")

            logger.debug(f"Surya обработка: {input_path}")

            if input_path.suffix.lower() == ".pdf":
                text, ocr_items = self._process_pdf(input_path)
            else:
                text, ocr_items = self._process_image(input_path)

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(text, encoding="utf-8")

            duration = time.time() - start_time

            return OCRResult(
                success=True,
                text=text,
                confidence=0.0,
                duration=duration,
                engine=self.name,
                metadata={
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "lines": len(text.splitlines()),
                    "ocr_items": ocr_items,
                    "dpi": self.config.get("dpi", 200),
                },
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Surya ошибка: {e}")
            return OCRResult(
                success=False,
                text="",
                duration=duration,
                engine=self.name,
                error=str(e),
            )

    def _process_image(self, input_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        image = Image.open(input_path).convert("RGB")
        ocr_items = self._run_surya([image], page_offset=0)
        text = "\n".join(item["text"] for item in ocr_items if item.get("text")).strip()
        return text, ocr_items

    def _process_pdf(self, input_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        doc = fitz.open(str(input_path))
        dpi = int(self.config.get("dpi", 200))
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        images: List[Image.Image] = []
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(image)

        ocr_items = self._run_surya(images, page_offset=0)
        text = "\n\n".join(item["text"] for item in ocr_items if item.get("text")).strip()
        return text, ocr_items

    def _run_surya(self, images: List[Image.Image], page_offset: int = 0) -> List[Dict[str, Any]]:
        _, detector, recognizer = self._ensure_models()
        predictions = recognizer(images, det_predictor=detector)

        items: List[Dict[str, Any]] = []
        for local_page_index, page in enumerate(predictions):
            page_number = page_offset + local_page_index
            for line in page.text_lines:
                x1, y1, x2, y2 = line.bbox
                items.append(
                    {
                        "text": line.text.strip(),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "page": page_number,
                    }
                )
        return items
