# workers/LLM/src/llm/base.py
"""
Базовые интерфейсы для компонентов LLM.
Аналогично workers/OCR/src/ocr/base.py
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple


class ClassifierEngine(ABC):
    """
    Базовый интерфейс для классификатора документов.

    Все классификаторы должны реализовывать:
    - classify(text: str) → Tuple[str, float]
    """

    name: str = "base_classifier"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Классифицирует текст документа.

        Args:
            text: Текст документа из OCR

        Returns:
            Tuple[str, float]: (тип документа, уверенность 0.0..1.0)
        """
        pass


class ExtractorEngine(ABC):
    """
    Базовый интерфейс для экстрактора данных.

    Все экстракторы должны реализовывать:
    - extract(text: str, schema: dict, doc_type: str) → Optional[dict]
    """

    name: str = "base_extractor"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def extract(
        self,
        text: str,
        schema: Optional[Dict[str, Any]],
        doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Извлекает структурированные данные из текста.

        Args:
            text: Текст документа
            schema: JSON-схема для валидации
            doc_type: Тип документа

        Returns:
            Optional[Dict]: Извлечённые данные или None при ошибке
        """
        pass


class ConverterEngine(ABC):
    """
    Базовый интерфейс для конвертера данных.

    Все конвертеры должны реализовывать:
    - convert(data: dict, doc_type: str) → str
    """

    name: str = "base_converter"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def convert(self, data: Dict[str, Any], doc_type: str) -> str:
        """
        Конвертирует структурированные данные в целевой формат.

        Args:
            data: Извлечённые данные
            doc_type: Тип документа

        Returns:
            str: Сериализованные данные (XML/JSON и т.д.)
        """
        pass