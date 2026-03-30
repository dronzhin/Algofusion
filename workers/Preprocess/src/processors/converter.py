# workers/Preprocess/src/processors/converter.py
"""
Конвертер: PDF → PNG (все страницы, в память).
Только для контейнера processor.
"""

from pathlib import Path
from typing import List
from pdf2image import convert_from_path
from PIL import Image

from shared.utils.logger import setup_logger

logger = setup_logger("workers.Preprocess.processors.converter")


def convert_pdf_to_images(pdf_path: Path, dpi: int = 600) -> List[Image.Image]:
    """Конвертирует ВСЕ страницы PDF в список PIL.Image."""
    logger.info(f"📄 Конвертация всех страниц: {pdf_path.name} @ {dpi} DPI")

    images = convert_from_path(str(pdf_path), dpi=dpi)

    if not images:
        raise ValueError(f"PDF пустой: {pdf_path}")

    images_rgb = [img.convert("RGB") for img in images]
    logger.info(f"✅ Конвертировано страниц: {len(images_rgb)}")
    return images_rgb