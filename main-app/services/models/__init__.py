# services/models/__init__.py
"""
Универсальная архитектура для любых моделей через Ollama
Поддержка: текстовых, визуальных, мультимодальных и специализированных моделей
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Типы моделей"""
    TEXT = "text"  # Текстовые модели (только промпт)
    VISION = "vision"  # Визуальные модели (изображение + промпт)
    MULTIMODAL = "multimodal"  # Мультимодальные (текст + изображение + другие)
    OCR = "ocr"  # Специализированные для распознавания текста
    EMBEDDING = "embedding"  # Модели для эмбеддингов
    SPECIALIZED = "specialized"  # Специализированные модели (например, для кода)


class InputType(Enum):
    """Типы входных данных"""
    TEXT_ONLY = "text_only"
    IMAGE_ONLY = "image_only"
    TEXT_AND_IMAGE = "text_and_image"
    FILE = "file"
    CUSTOM = "custom"


@dataclass
class ModelInput:
    """Унифицированный класс входных данных"""
    text: Optional[str] = None
    image_base64: Optional[str] = None
    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


@dataclass
class ModelOutput:
    """Унифицированный класс выходных данных"""
    text: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    processing_time: Optional[float] = None


class ModelBase(ABC):
    """Базовый класс для всех моделей"""

    # Метаданные модели
    model_name: str = "base-model"
    display_name: str = "Базовая модель"
    model_type: ModelType = ModelType.TEXT
    input_type: InputType = InputType.TEXT_ONLY

    # Возможности модели
    supports_streaming: bool = False
    supports_confidence: bool = False
    supports_multilingual: bool = True
    supports_system_prompt: bool = True

    # Настройки по умолчанию
    default_prompt: str = "You are a helpful assistant."
    default_temperature: float = 0.7
    default_max_tokens: int = 2048

    # Описание
    description: str = "Базовая модель"
    use_cases: List[str] = None
    languages: List[str] = None

    def __init__(self, ollama_base_url: str, timeout: int):
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.timeout = timeout
        self.use_cases = self.use_cases or []
        self.languages = self.languages or ["en", "ru"]

    @abstractmethod
    def prepare_request(
            self,
            input_data: ModelInput,
            **kwargs
    ) -> Dict[str, Any]:
        """
        Подготовка запроса к Ollama

        Args:
            input_data: входные данные
            **kwargs: дополнительные параметры (temperature, max_tokens и т.д.)

        Returns:
            Словарь с данными запроса для Ollama API
        """
        pass

    @abstractmethod
    def parse_response(self, response_json: Dict[str, Any]) -> ModelOutput:
        """
        Парсинг ответа от модели

        Args:
            response_json: JSON ответ от Ollama

        Returns:
            Объект ModelOutput с результатами
        """
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """Получение возможностей модели"""
        return {
            "supports_streaming": self.supports_streaming,
            "supports_confidence": self.supports_confidence,
            "supports_multilingual": self.supports_multilingual,
            "supports_system_prompt": self.supports_system_prompt,
            "input_type": self.input_type.value,
            "model_type": self.model_type.value
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Получение метаданных модели для отображения в UI"""
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "model_type": self.model_type.value,
            "input_type": self.input_type.value,
            "description": self.description,
            "use_cases": self.use_cases,
            "languages": self.languages,
            "default_prompt": self.default_prompt,
            "default_temperature": self.default_temperature,
            "default_max_tokens": self.default_max_tokens,
            **self.get_capabilities()
        }

    def validate_input(self, input_data: ModelInput) -> bool:
        """
        Валидация входных данных

        По умолчанию проверяет соответствие типа входных данных
        """
        # Базовая валидация
        if self.input_type == InputType.TEXT_ONLY and not input_data.text:
            raise ValueError("Текстовая модель требует текстовый ввод")

        if self.input_type == InputType.IMAGE_ONLY and not input_data.image_base64:
            raise ValueError("Визуальная модель требует изображение")

        if self.input_type == InputType.TEXT_AND_IMAGE:
            if not input_data.text and not input_data.image_base64:
                raise ValueError("Мультимодальная модель требует текст или изображение")

        return True

    @property
    def is_text_model(self) -> bool:
        """Является ли модель текстовой"""
        return self.model_type in [ModelType.TEXT, ModelType.MULTIMODAL]

    @property
    def is_vision_model(self) -> bool:
        """Является ли модель визуальной"""
        return self.model_type in [ModelType.VISION, ModelType.OCR, ModelType.MULTIMODAL]