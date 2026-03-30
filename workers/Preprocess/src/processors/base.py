# workers/Preprocess/src/processors/base.py
"""
Базовый интерфейс для процессоров изображений.
Только для контейнера processor.
"""

from abc import ABC, abstractmethod
from typing import List
from PIL import Image


class ImageProcessorStep(ABC):
    """Базовый класс для шага обработки изображения в памяти."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, img: Image.Image) -> Image.Image:
        """Обрабатывает одно изображение в памяти."""
        pass

    def process_batch(self, images: List[Image.Image]) -> List[Image.Image]:
        """Обрабатывает список изображений (реализация по умолчанию)."""
        return [self.process(img) for img in images]