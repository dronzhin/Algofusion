# workers/Preprocess/src/config.py
"""
Настройки модуля обработки изображений.
Только для контейнера processor.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple
import os


@dataclass
class ImageProcessingConfig:
    """Конфигурация обработки изображений."""

    # Конвертация
    pdf_dpi: int = int(os.getenv("PROCESSOR_PDF_DPI", "600"))
    supported_input_formats: Tuple[str, ...] = field(default_factory=lambda: (
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"
    ))
    output_format: str = "png"

    # Бинаризация
    background_threshold: int = int(os.getenv("PROCESSOR_BG_THRESHOLD", "128"))
    binary_threshold: int = int(os.getenv("PROCESSOR_BIN_THRESHOLD", "128"))
    median_filter_iterations: int = int(os.getenv("PROCESSOR_MEDIAN_ITER", "5"))
    median_filter_size: int = int(os.getenv("PROCESSOR_MEDIAN_SIZE", "3"))

    # Поворот
    rotation_angle_threshold: float = float(os.getenv("PROCESSOR_ROT_ANGLE_THRESH", "0.5"))
    rotation_scale: float = float(os.getenv("PROCESSOR_ROT_SCALE", "1.0"))
    use_otsu_for_rotation: bool = os.getenv("PROCESSOR_USE_OTSU", "1") == "1"

    # Пути
    work_dir: Path = Path(os.getenv("PROCESSOR_WORK_DIR", "/tmp/algofusion_work"))

    def get_stage_dirs(self) -> dict[str, Path]:
        """Возвращает словари путей для этапов обработки."""
        base = self.work_dir
        return {
            "converted": base / "converted",
            "binarized": base / "binarized",
            "rotated": base / "rotated",
            "final": base / "final",
        }