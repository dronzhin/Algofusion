# workers/Preprocess/src/processors/converter.py
"""
Конвертер: PDF → PNG.
Только для контейнера processor.
"""

from pathlib import Path
from pdf2image import convert_from_path

from shared.utils.logger import setup_logger

logger = setup_logger("processor.converters.pdf_to_png")


def convert_pdf_to_png(
        pdf_path: Path,
        output_dir: Path,
        dpi: int = 600,
        output_prefix: str | None = None
) -> list[Path]:
    """Конвертирует PDF в набор PNG изображений."""
    logger.info(f"📄 Конвертация PDF: {pdf_path.name} @ {dpi} DPI")

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_prefix or pdf_path.stem

    try:
        images = convert_from_path(str(pdf_path), dpi=dpi)

        output_paths = []
        for page_num, image in enumerate(images, start=1):
            filename = f"{prefix}_page_{page_num}.png"
            output_path = output_dir / filename
            image.save(output_path, format="PNG", compress_level=0)
            output_paths.append(output_path)
            logger.debug(f"✅ Страница {page_num}: {filename}")

        logger.info(f"✅ Конвертация завершена: {len(output_paths)} страниц")
        return output_paths

    except Exception as e:
        logger.error(f"❌ Ошибка конвертации {pdf_path.name}: {e}")
        raise