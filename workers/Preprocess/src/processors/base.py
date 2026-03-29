# workers/Preprocess/src/processors/base.py
"""
Базовый интерфейс для процессоров изображений.
Только для контейнера processor.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class ImageProcessorStep(ABC):
    """Базовый класс для шага обработки изображения."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, input_path: Path, output_path: Path) -> Path:
        """Обрабатывает изображение."""
        pass

    @abstractmethod
    def validate_input(self, input_path: Path) -> bool:
        """Проверяет, может ли процессор обработать файл."""
        pass