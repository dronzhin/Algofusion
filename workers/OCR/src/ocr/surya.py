# workers/OCR/src/ocr/surya.py
"""
Surya OCR движок (распознавание в памяти).
"""

from typing import List, Optional
from PIL import Image

from shared.utils.logger import setup_logger
from workers.OCR.src.ocr.base import OCREngine
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor

logger = setup_logger("workers.ocr.ocr.surya")


class SuryaEngine(OCREngine):
    """
    Surya OCR с обработкой в памяти.

    🔹 Только распознавание: PIL.Image → str
    🔹 Модели загружаются лениво и кэшируются на уровне класса
    🔹 Поддержка нескольких языков через список
    """

    name = "surya"

    # 🔹 Кэш моделей на уровне класса (не создаём заново для каждого экземпляра)
    _recognizer: Optional["RecognitionPredictor"] = None
    _detector: Optional["DetectionPredictor"] = None

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
        if cls._detector is None:
            logger.info("🔤 Загрузка детектора Surya...")
            cls._detector = DetectionPredictor()

        if cls._recognizer is None:
            logger.info("🔤 Загрузка распознавателя Surya...")
            cls._recognizer = RecognitionPredictor()

        return cls._recognizer, cls._detector

    def process(self, img: Image.Image) -> str:
        """
        Распознаёт текст на одном изображении в памяти.

        Args:
            img: PIL.Image (RGB)

        Returns:
            str: Распознанный текст
        """
        logger.debug(f"🔤 Surya: {img.size}px, режим={img.mode}")

        # 🔹 Конвертируем в RGB если нужно
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 🔹 Загружаем модели при первом вызове
        recognizer, detector = self._ensure_models()

        # 🔹 Запуск распознавания (Surya принимает список PIL-изображений)
        predictions = recognizer([img], det_predictor=detector)

        # 🔹 Извлекаем текст из предсказаний
        text_lines = []
        for page_pred in predictions:
            for line in page_pred.text_lines:
                if line.text and line.text.strip():
                    text_lines.append(line.text.strip())

        result = "\n".join(text_lines)
        logger.debug(f"✅ Surya: {len(result)} символов")
        return result

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """
        Пакетная обработка: Surya эффективнее обрабатывает несколько изображений за один вызов.
        """
        if not images:
            return []

        logger.info(f"🔤 Surya: пакетная обработка {len(images)} изображений")

        # 🔹 Конвертируем все изображения в RGB
        rgb_images = [
            img.convert("RGB") if img.mode != "RGB" else img
            for img in images
        ]

        # 🔹 Загружаем модели
        recognizer, detector = self._ensure_models()

        # 🔹 Один вызов для всех изображений
        predictions = recognizer(rgb_images, det_predictor=detector)

        # 🔹 Извлекаем текст для каждого изображения
        results = []
        for page_pred in predictions:
            text_lines = [
                line.text.strip()
                for line in page_pred.text_lines
                if line.text and line.text.strip()
            ]
            results.append("\n".join(text_lines))

        logger.debug(f"✅ Surya batch: обработано {len(results)} изображений")
        return results