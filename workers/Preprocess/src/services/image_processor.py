# workers/Preprocess/src/services/image_processor.py
"""
Сервис обработки изображений.
Оркестрирует пайплайн: конвертация → бинаризация → поворот.
Только для контейнера processor.
"""

from pathlib import Path
from typing import Optional
import shutil

from shared.utils.logger import setup_logger
from shared.models.file import FileJob, FileStatus
from workers.Preprocess.src.config import ImageProcessingConfig
from workers.Preprocess.src.processors.converter import convert_pdf_to_png
from workers.Preprocess.src.processors.binarizer import Binarizer
from workers.Preprocess.src.processors.rotator import Rotator

logger = setup_logger("processor.services.image_processor")


class ImageProcessingError(Exception):
    """Исключение при ошибке обработки."""
    pass


class ImageProcessor:
    """
    Сервис обработки: конвертация → бинаризация → поворот.

    Вход: любой поддерживаемый формат
    Выход: PNG (бинаризованное, выровненное)
    """

    def __init__(self, config: Optional[ImageProcessingConfig] = None):
        self.config = config or ImageProcessingConfig()

        self.binarizer = Binarizer(
            background_threshold=self.config.background_threshold,
            binary_threshold=self.config.binary_threshold,
            median_iterations=self.config.median_filter_iterations,
            median_size=self.config.median_filter_size,
        )

        self.rotator = Rotator(
            angle_threshold=self.config.rotation_angle_threshold,
            scale=self.config.rotation_scale,
            use_otsu=self.config.use_otsu_for_rotation,
        )

    def _is_supported_format(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.config.supported_input_formats

    def _ensure_work_dirs(self) -> dict[str, Path]:
        dirs = self.config.get_stage_dirs()
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return dirs

    def _cleanup_work_dirs(self, dirs: dict[str, Path]):
        for path in dirs.values():
            if path.exists():
                shutil.rmtree(path)

    def process_file_job(
            self,
            job: FileJob,
            file_service,  # FileService из core.services
            cleanup_temp: bool = True,
    ) -> Optional[Path]:
        """
        Полный пайплайн обработки файла.

        Сохраняет результат в preprocessed/ через file_service.
        """
        original_path = file_service.get_download_path(job.file_id, "original")
        if not original_path or not original_path.exists():
            logger.error(f"Оригинал не найден: {job.file_id}")
            return None

        if not self._is_supported_format(original_path):
            logger.error(f"Неподдерживаемый формат: {original_path.suffix}")
            return None

        work_dirs = self._ensure_work_dirs()

        try:
            # Шаг 1: Конвертация (если PDF)
            if original_path.suffix.lower() == ".pdf":
                logger.info(f"📄 PDF→PNG: {original_path.name}")
                png_paths = convert_pdf_to_png(
                    original_path,
                    work_dirs["converted"],
                    dpi=self.config.pdf_dpi,
                    output_prefix=job.file_id
                )
                input_path = png_paths[0]  # Обрабатываем первую страницу
            else:
                input_path = original_path

            # Шаг 2: Бинаризация
            binarized_path = work_dirs["binarized"] / f"{job.file_id}.png"
            self.binarizer.process(input_path, binarized_path)

            # Шаг 3: Поворот
            rotated_path = work_dirs["rotated"] / f"{job.file_id}.png"
            self.rotator.process(binarized_path, rotated_path)

            # Шаг 4: Сохранение в preprocessed/
            preprocessed_dir = Path(file_service.base_dir) / job.file_id / "preprocessed"
            preprocessed_dir.mkdir(parents=True, exist_ok=True)
            final_path = preprocessed_dir / f"{job.file_id}_processed.png"
            shutil.copy2(rotated_path, final_path)

            logger.info(f"✅ Обработка завершена: {final_path.name}")
            return final_path

        except Exception as e:
            logger.error(f"❌ Ошибка обработки {job.file_id}: {e}", exc_info=True)
            raise ImageProcessingError(f"Обработка не удалась: {e}")

        finally:
            if cleanup_temp:
                self._cleanup_work_dirs(work_dirs)