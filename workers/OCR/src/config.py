# workers/ocr/src/config.py
"""
Конфигурация OCR-воркера.
Только необходимые параметры, без дублирования.
"""

from dataclasses import dataclass, field
import os


@dataclass
class OCRProcessingConfig:
    """Конфигурация обработки OCR (в памяти)."""

    # === Движок по умолчанию ===
    default_engine: str = os.getenv("OCR_DEFAULT_ENGINE", "tesseract")
    default_lang: str = os.getenv("OCR_DEFAULT_LANG", "rus+eng")

    # === Tesseract параметры ===
    tesseract_oem: int = int(os.getenv("OCR_TESSERACT_OEM", "1"))
    tesseract_psm: int = int(os.getenv("OCR_TESSERACT_PSM", "11"))
    tesseract_preprocess: bool = os.getenv("OCR_TESSERACT_PREPROCESS", "0") == "1"
    tesseract_dpi: int = int(os.getenv("OCR_TESSERACT_DPI", "300"))

    # === EasyOCR параметры ===
    easyocr_gpu: bool = os.getenv("OCR_EASYOCR_GPU", "0") == "1"
    easyocr_min_score: float = float(os.getenv("OCR_EASYOCR_MIN_SCORE", "0.5"))

    # === Общие ===
    supported_input_formats: tuple[str, ...] = field(default_factory=lambda: (
        ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"
    ))
    output_extension: str = ".txt"