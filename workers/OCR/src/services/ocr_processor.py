# workers/OCR/services/ocr_processor.py
"""
Сервис OCR-обработки.
Пайплайн: загрузка → распознавание → сохранение.
Все шаги выполняются в памяти.
"""

from pathlib import Path
from typing import List
from PIL import Image

from shared.utils.logger import setup_logger
from shared.models.file import FileJob
from workers.OCR.src.config import OCRProcessingConfig
from workers.OCR.src.ocr.tesseract import TesseractEngine
from workers.OCR.src.ocr.easyocr import EasyOCREngine

logger = setup_logger("workers.ocr.services.ocr_processor")


class OCRProcessingError(Exception):
    """Исключение при ошибке OCR-обработки."""
    pass


class OCRProcessor:
    """
    OCR-обработка в памяти.

    Пайплайн:
    1. Загрузка изображений из preprocessed/ (PIL.Image)
    2. Распознавание текста (в памяти)
    3. Сохранение результатов в ocr/ как {file_id}_page_{N}.txt
    """

    def __init__(self, config: OCRProcessingConfig):
        self.config = config

        # Инициализируем движок
        engine_name = config.default_engine

        engine_config = {
            "lang": config.default_lang,
            "oem": config.tesseract_oem,
            "psm": config.tesseract_psm,
            "preprocess": config.tesseract_preprocess,
            "gpu": config.easyocr_gpu,
            "min_score": config.easyocr_min_score,
        }

        if engine_name == "tesseract":
            self.engine = TesseractEngine(engine_config)
        elif engine_name == "easyocr":
            # Для EasyOCR нужен список языков
            engine_config["lang"] = config.default_lang.split("+") if "+" in config.default_lang else [config.default_lang]
            self.engine = EasyOCREngine(engine_config)
        else:
            raise ValueError(f"Неизвестный OCR движок: {engine_name}")

    def process(self, job: FileJob, file_service) -> List[Path]:
        """
        Полный пайплайн OCR-обработки (все страницы).

        Args:
            job: FileJob с метаданными
            file_service: FileService для работы с путями

        Returns:
            list[Path]: Пути к созданным файлам в ocr/

        Raises:
            OCRProcessingError: При ошибке обработки
        """
        # 🔹 Получаем путь к preprocessed/ (результат предобработки)
        preprocessed_dir = Path(file_service.base_dir) / job.file_id / "preprocessed"
        if not preprocessed_dir.exists():
            raise OCRProcessingError(f"preprocessed/ не найден: {job.file_id}")

        # 🔹 Загружаем все обработанные изображения в память
        image_paths = sorted(preprocessed_dir.glob(f"{job.file_id}_page_*.png"))
        if not image_paths:
            raise OCRProcessingError(f"Нет файлов для OCR: {preprocessed_dir}")

        logger.info(f"🎯 OCR файла: {job.file_id} ({len(image_paths)} страниц)")

        images = [Image.open(p).convert("RGB") for p in image_paths]

        # 🔹 Распознавание текста (в памяти)
        texts: List[str] = self.engine.process_batch(images)

        # 🔹 Сохранение результатов в ocr/
        ocr_dir = Path(file_service.base_dir) / job.file_id / "ocr"
        ocr_dir.mkdir(parents=True, exist_ok=True)

        output_paths = []
        for page_num, (img_path, text) in enumerate(zip(image_paths, texts), start=1):
            # Имя файла: {file_id}_page_{N}.txt (аналогично preprocess)
            output_path = ocr_dir / f"{job.file_id}_page_{page_num}.txt"
            output_path.write_text(text, encoding="utf-8")
            output_paths.append(output_path)
            logger.debug(f"✅ Сохранена страница {page_num}: {output_path.name} ({len(text)} симв.)")

        logger.info(f"✅ OCR завершён: {len(output_paths)} файлов")
        return output_paths