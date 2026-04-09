#!/usr/bin/env python3
# workers/LLM/schemas/base.py
"""
Базовый класс для схем документов.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import json


class BaseSchema(ABC):
    """Абстрактный базовый класс для схем документов."""

    document_type: str = "unknown"

    def __init__(self, schema_path: Optional[Path] = None):
        self.schema_path = schema_path
        self._data: Optional[Dict[str, Any]] = None
        self._loaded = False

    def _load_data(self) -> Dict[str, Any]:
        """Ленивая загрузка схемы из файла."""
        if not self._loaded and self.schema_path and self.schema_path.exists():
            try:
                with open(self.schema_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as e:
                from shared.utils.logger import setup_logger
                logger = setup_logger("workers.llm.schemas")
                logger.error(f"❌ Ошибка загрузки схемы {self.schema_path}: {e}")
                self._data = {}
        self._loaded = True
        return self._data or {}

    @property
    def json_schema(self) -> Dict[str, Any]:
        """Возвращает JSON Schema для валидации."""
        return self._load_data().get("json_schema", {})

    @property
    def example(self) -> Dict[str, Any]:
        """Возвращает пример вывода (для промпта)."""
        return self._load_data().get("example", {})

    @property
    def prompt_hints(self) -> str:
        """Дополнительные инструкции для LLM."""
        return self._load_data().get("prompt_hints", "")

    @property
    def description(self) -> str:
        """Описание типа документа."""
        return self._load_data().get("description", "")

    def get_fields_description(self) -> Dict[str, str]:
        """Возвращает {поле: описание} для формирования промпта."""
        properties = self.json_schema.get("properties", {})
        return {
            name: prop.get("description", prop.get("type", "any"))
            for name, prop in properties.items()
        }

    def get_required_fields(self) -> List[str]:
        """Список обязательных полей."""
        return self.json_schema.get("required", [])

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """Валидирует извлечённые данные против схемы."""
        pass

    def format_example_for_prompt(self) -> str:
        """Форматирует пример для вставки в промпт."""
        if not self.example:
            return ""
        return json.dumps(self.example, ensure_ascii=False, indent=2)