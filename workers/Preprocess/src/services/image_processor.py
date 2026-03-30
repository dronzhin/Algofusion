# workers/Preprocess/src/services/image_processor.py
"""
Сервис обработки изображений.
Пайплайн: загрузка → бинаризация → поворот → сохранение.
Обрабатывает ВСЕ страницы PDF.
Все шаги выполняются в памяти.
Только для контейнера processor.
"""

from pathlib import Path
from typing import List

from PIL import Image

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
from workers.Preprocess.src.config import ImageProcessingConfig
from workers.Preprocess.src.processors.converter import convert_pdf_to_images
from workers.Preprocess.src.processors.binarizer import Binarizer
from workers.Preprocess.src.processors.rotator import Rotator

logger = setup_logger("workers.Preprocess.services.image_processor")


class ImageProcessingError(Exception):
    """Исключение при ошибке обработки изображения."""
    pass


class ImageProcessor:
    """Обработка изображений в памяти."""

    def __init__(self, config: ImageProcessingConfig):
        self.config = config

        self.binarizer = Binarizer(
            background_threshold=config.background_threshold,
            binary_threshold=config.binary_threshold,
            median_iterations=config.median_filter_iterations,
            median_size=config.median_filter_size,
        )

        self.rotator = Rotator(
            angle_threshold=config.rotation_angle_threshold,
            scale=config.rotation_scale,
        )

    def process(self, job: FileJob, file_service) -> List[Path]:
        """Полный пайплайн обработки файла (ВСЕ страницы для PDF)."""
        original_path = file_service.get_download_path(job.file_id, "original")
        if not original_path or not original_path.exists():
            raise ImageProcessingError(f"Оригинал не найден: {job.file_id}")

        logger.info(f"🎯 Обработка файла: {job.file_id} ({job.original_filename})")

        # Загрузка изображений в память
        if original_path.suffix.lower() == ".pdf":
            images = convert_pdf_to_images(original_path, dpi=self.config.pdf_dpi)
        else:
            img = Image.open(original_path).convert("RGB")
            images = [img]

        logger.info(f"📄 Страниц для обработки: {len(images)}")

        # Бинаризация всех страниц
        images = self.binarizer.process_batch(images)

        # Поворот всех страниц
        images = self.rotator.process_batch(images)

        # Сохранение всех страниц
        output_dir = Path(file_service.base_dir) / job.file_id / "preprocessed"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths = []
        for page_num, img in enumerate(images, start=1):
            output_path = output_dir / f"{job.file_id}_page_{page_num}.png"
            img.save(output_path, format="PNG", compress_level=6)
            output_paths.append(output_path)
            logger.debug(f"✅ Сохранена страница {page_num}: {output_path.name}")

        logger.info(f"✅ Обработка завершена: {len(output_paths)} страниц")
        return output_paths