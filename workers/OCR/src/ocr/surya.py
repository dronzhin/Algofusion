#!/usr/bin/env python3
# workers/OCR/src/ocr/surya.py
"""
Surya OCR движок (распознавание в памяти).
✅ Гарантированная поддержка нового API (Surya >=0.8.0)
"""

from typing import List, Optional
from PIL import Image

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine

logger = setup_logger("workers.ocr.ocr.surya")


class SuryaEngine(OCREngine):
    """
    Surya OCR с обработкой в памяти.
    🔹 Только распознавание: PIL.Image → str
    🔹 Всегда использует новый API с FoundationPredictor
    🔹 Кэширование всех моделей на уровне класса
    """

    name = "surya"

    # 🔹 Кэш моделей на уровне класса
    _recognizer = None
    _detector = None
    _foundation = None

    def __init__(self, config: dict):
        super().__init__(config)

        # 🔹 Языки: преобразуем "rus+eng" → ["rus", "eng"]
        lang_config = config.get("lang", "rus+eng")
        if isinstance(lang_config, str):
            self.lang_list = lang_config.split("+")
        else:
            self.lang_list = list(lang_config)

        logger.info(f"🔤 Surya инициализирован: языки={self.lang_list}")

    @classmethod
    def _ensure_models(cls):
        """Загрузка моделей Surya (новый API с FoundationPredictor)."""

        # 🔹 1. Детектор
        if cls._detector is None:
            logger.info("🔤 Загрузка детектора Surya...")
            from surya.detection import DetectionPredictor
            cls._detector = DetectionPredictor()

        # 🔹 2. Foundation Predictor (обязателен для нового API)
        if cls._foundation is None:
            logger.info("🔤 Загрузка FoundationPredictor для Surya...")
            # 🔹 Пробуем разные пути импорта для совместимости
            try:
                from surya.model import FoundationPredictor
            except ImportError:
                try:
                    from surya.foundation import FoundationPredictor
                except ImportError:
                    from surya.models import FoundationPredictor
            cls._foundation = FoundationPredictor()

        # 🔹 3. Распознаватель (всегда с foundation_predictor)
        if cls._recognizer is None:
            logger.info("🔤 Загрузка распознавателя Surya...")
            from surya.recognition import RecognitionPredictor
            # 🔹 КЛЮЧЕВОЕ: всегда передаём foundation_predictor
            cls._recognizer = RecognitionPredictor(
                foundation_predictor=cls._foundation
            )

        return cls._recognizer, cls._detector

    def process(self, img: Image.Image) -> str:
        """Распознаёт текст на одном изображении в памяти."""
        logger.debug(f"🔤 Surya: {img.size}px, режим={img.mode}")

        if img.mode != "RGB":
            img = img.convert("RGB")

        recognizer, detector = self._ensure_models()

        # 🔹 Запуск распознавания с языками
        predictions = recognizer(
            [img],
            det_predictor=detector,
            langs=[self.lang_list]  # 🔹 Новый API требует список списков
        )

        # 🔹 Извлекаем текст с защитой от None
        text_lines = []
        for page_pred in predictions:
            for line in getattr(page_pred, 'text_lines', []):
                text = getattr(line, 'text', None)
                if text and text.strip():
                    text_lines.append(text.strip())

        result = "\n".join(text_lines)
        logger.debug(f"✅ Surya: {len(result)} символов")
        return result

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """Пакетная обработка изображений."""
        if not images:
            return []

        logger.info(f"🔤 Surya: пакетная обработка {len(images)} изображений")

        # 🔹 Конвертируем в RGB
        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img
            for img in images
        ]

        recognizer, detector = self._ensure_models()

        # 🔹 Вызов с языками (новый API)
        predictions = recognizer(
            rgb_images,
            det_predictor=detector,
            langs=[self.lang_list]
        )

        # 🔹 Извлекаем текст для каждого изображения
        results = []
        for page_pred in predictions:
            text_lines = [
                line.text.strip()
                for line in getattr(page_pred, 'text_lines', [])
                if getattr(line, 'text', None) and getattr(line, 'text', '').strip()
            ]
            results.append("\n".join(text_lines))

        logger.debug(f"✅ Surya batch: обработано {len(results)} изображений")
        return results