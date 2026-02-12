# services/models/factory.py
"""
Универсальная фабрика для любых типов моделей
"""

from typing import Dict, Type, Optional, List
from enum import Enum
from . import ModelBase, ModelType
from .text_models import (
    Llama3TextModel,
    QwenTextModel,
    Phi3TextModel,
    CodeLlamaModel
)
from .vision_models import (
    GlmOcrModel,
    LlavaVisionModel,
    MoondreamVisionModel
)
import logging

logger = logging.getLogger(__name__)


class ModelCategory(Enum):
    """Категории моделей для группировки в UI"""
    OCR = "ocr"
    TEXT_GENERAL = "text_general"
    TEXT_CODE = "text_code"
    VISION = "vision"
    SPECIALIZED = "specialized"


class ModelFactory:
    """Универсальная фабрика для создания и управления моделями"""

    # Регистр моделей: имя_модели -> класс
    _model_registry: Dict[str, Type[ModelBase]] = {}

    # Категории моделей
    _model_categories: Dict[str, ModelCategory] = {}

    # Псевдонимы для удобного выбора
    _model_aliases: Dict[str, str] = {}

    @classmethod
    def register_model(
            cls,
            model_name: str,
            model_class: Type[ModelBase],
            category: Optional[ModelCategory] = None,
            alias: Optional[str] = None
    ):
        """
        Регистрация новой модели

        Пример:
            ModelFactory.register_model(
                "my-model:latest",
                MyCustomModel,
                category=ModelCategory.TEXT_GENERAL,
                alias="my-model"
            )
        """
        if not issubclass(model_class, ModelBase):
            raise ValueError(f"{model_class} должен быть подклассом ModelBase")

        cls._model_registry[model_name] = model_class

        # Определение категории по типу модели, если не указана
        if category is None:
            model_type = model_class.model_type
            if model_type == ModelType.OCR:
                category = ModelCategory.OCR
            elif model_type == ModelType.TEXT:
                if "code" in model_class.display_name.lower():
                    category = ModelCategory.TEXT_CODE
                else:
                    category = ModelCategory.TEXT_GENERAL
            elif model_type in [ModelType.VISION, ModelType.MULTIMODAL]:
                category = ModelCategory.VISION
            else:
                category = ModelCategory.SPECIALIZED

        cls._model_categories[model_name] = category

        # Регистрация псевдонима
        if alias:
            cls._model_aliases[alias] = model_name

        logger.info(
            f"Зарегистрирована модель: {model_name} "
            f"(категория: {category.value}, класс: {model_class.__name__})"
        )

    @classmethod
    def register_models_bulk(cls, models_config: List[tuple]):
        """
        Массовая регистрация моделей

        Пример:
            ModelFactory.register_models_bulk([
                ("llama3:latest", Llama3TextModel, ModelCategory.TEXT_GENERAL, "llama3"),
                ("glm-ocr:latest", GlmOcrModel, ModelCategory.OCR, "glm-ocr"),
            ])
        """
        for config in models_config:
            model_name = config[0]
            model_class = config[1]
            category = config[2] if len(config) > 2 else None
            alias = config[3] if len(config) > 3 else None

            cls.register_model(model_name, model_class, category, alias)

    @classmethod
    def create_model(
            cls,
            model_identifier: str,
            ollama_base_url: str,
            timeout: int
    ) -> Optional[ModelBase]:
        """
        Создание экземпляра модели по идентификатору

        Args:
            model_identifier: имя модели или псевдоним
            ollama_base_url: базовый URL Ollama
            timeout: таймаут запроса

        Returns:
            Экземпляр модели или None если не найдена
        """
        # Разрешение псевдонимов
        model_key = cls._model_aliases.get(model_identifier, model_identifier)

        # Поиск в реестре
        model_class = cls._model_registry.get(model_key)

        if not model_class:
            logger.warning(f"Модель '{model_identifier}' не найдена")
            return None

        try:
            return model_class(ollama_base_url, timeout)
        except Exception as e:
            logger.error(f"Ошибка создания модели {model_identifier}: {e}")
            return None

    @classmethod
    def get_available_models(
            cls,
            model_type: Optional[ModelType] = None,
            category: Optional[ModelCategory] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Получение списка доступных моделей с фильтрацией

        Args:
            model_type: фильтр по типу модели
            category: фильтр по категории

        Returns:
            Словарь: имя_модели -> метаданные
        """
        models_info = {}

        for model_name, model_class in cls._model_registry.items():
            # Фильтрация по типу
            if model_type and model_class.model_type != model_type:
                continue

            # Фильтрация по категории
            if category and cls._model_categories.get(model_name) != category:
                continue

            try:
                instance = model_class("", 0)
                info = instance.get_model_info()
                info["category"] = cls._model_categories.get(model_name, ModelCategory.SPECIALIZED).value
                models_info[model_name] = info
            except Exception as e:
                logger.error(f"Ошибка получения метаданных для {model_name}: {e}")
                continue

        return models_info

    @classmethod
    def get_models_by_category(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Группировка моделей по категориям"""
        categorized = {}

        for category in ModelCategory:
            categorized[category.value] = []

        models_info = cls.get_available_models()

        for model_name, info in models_info.items():
            category = info.get("category", "specialized")
            categorized[category].append(info)

        return categorized

    @classmethod
    def get_model_aliases(cls) -> Dict[str, str]:
        """Получение списка псевдонимов"""
        return cls._model_aliases.copy()

    @classmethod
    def get_default_model(cls, model_type: ModelType = ModelType.TEXT) -> str:
        """Получение имени модели по умолчанию для типа"""
        models = cls.get_available_models(model_type=model_type)
        if models:
            return next(iter(models.keys()))
        return "llama3:latest"

    @classmethod
    def initialize_default_models(cls):
        """Инициализация стандартных моделей"""
        cls.register_models_bulk([
            # Текстовые модели
            ("llama3:latest", Llama3TextModel, ModelCategory.TEXT_GENERAL, "llama3"),
            ("qwen:latest", QwenTextModel, ModelCategory.TEXT_GENERAL, "qwen"),
            ("phi3:latest", Phi3TextModel, ModelCategory.TEXT_GENERAL, "phi3"),
            ("codellama:latest", CodeLlamaModel, ModelCategory.TEXT_CODE, "codellama"),

            # OCR модели
            ("glm-ocr:latest", GlmOcrModel, ModelCategory.OCR, "glm-ocr"),

            # Визуальные модели
            ("llava:latest", LlavaVisionModel, ModelCategory.VISION, "llava"),
            ("moondream:latest", MoondreamVisionModel, ModelCategory.VISION, "moondream"),
        ])


# Автоматическая инициализация при импорте
ModelFactory.initialize_default_models()