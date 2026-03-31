# workers/ocr/src/ocr/base.py
"""
Базовый интерфейс для OCR-движков.
Работа в памяти: PIL.Image → str.
"""

from abc import ABC, abstractmethod
from typing import List, Union
from PIL import Image


class OCREngine(ABC):
    """
    Базовый класс для OCR-движка.

    Все движки должны реализовывать:
    - process(img: Image.Image) → str
    - process_batch(images: List[Image.Image]) → List[str]
    """

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def process(self, img: Image.Image) -> str:
        """
        Распознаёт текст на одном изображении.

        Args:
            img: PIL.Image (RGB или L)

        Returns:
            str: Распознанный текст
        """
        pass

    def process_batch(self, images: List[Image.Image]) -> List[str]:
        """
        Распознаёт текст на списке изображений (реализация по умолчанию).

        Движки могут переопределить для оптимизации.
        """
        return [self.process(img) for img in images]