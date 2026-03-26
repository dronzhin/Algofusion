# workers/ocr/src/ocr/registry.py
"""Реестр OCR движков."""

from typing import Dict, Optional, Type

from src.ocr.base import BaseOCREngine


class OCREngineRegistry:
    """Реестр доступных OCR движков."""

    _engines: Dict[str, Type[BaseOCREngine]] = {}

    @classmethod
    def register(cls, engine_class: Type[BaseOCREngine]) -> Type[BaseOCREngine]:
        """Декоратор для регистрации OCR движка."""
        if not engine_class.name:
            raise ValueError("OCR движок должен иметь атрибут 'name'")

        cls._engines[engine_class.name] = engine_class
        return engine_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseOCREngine]]:
        """Получить класс движка по имени."""
        return cls._engines.get(name)

    @classmethod
    def list_available(cls) -> Dict[str, str]:
        """Список доступных движков."""
        return {
            name: engine.description
            for name, engine in cls._engines.items()
        }

    @classmethod
    def create(cls, name: str, config: dict = None) -> BaseOCREngine:
        """Создать экземпляр OCR движка."""
        engine_class = cls.get(name)
        if not engine_class:
            available = ", ".join(cls._engines.keys())
            raise ValueError(
                f"Неизвестный OCR движок: {name}. Доступные: {available}"
            )
        return engine_class(config=config)

    @classmethod
    def is_available(cls, name: str) -> bool:
        """Проверить доступность движка."""
        return name in cls._engines
