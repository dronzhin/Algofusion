# workers/LLM/schemas/base.py
"""
Базовый класс для схем документов.
Аналогично OCR base.py
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class SchemaRegistry(ABC):
    """Абстрактный базовый класс для схемы документа."""

    doc_type: str = "unknown"
    description: str = "Базовая схема документа"

    @abstractmethod
    def get_json_schema(self) -> Dict[str, Any]:
        """Возвращает JSON Schema для валидации."""
        pass

    @abstractmethod
    def get_extraction_fields(self) -> List[str]:
        """Возвращает список обязательных полей."""
        pass

    @abstractmethod
    def get_prompt_hints(self) -> str:
        """Возвращает подсказки для промпта."""
        pass

    def validate(self, Dict[str, Any]

    ) -> Tuple[bool, List[str]]:
    """Базовая валидация данных."""
    errors = []
    required = self.get_extraction_fields()

    for field in required:
        if field not in
            errors.append(f"Отсутствует поле: {field}")

    return len(errors) == 0, errors


def to_xml_tag_name(self, field: str) -> str:
    """Конвертирует имя поля в XML-тег."""
    return ''.join(part.capitalize() for part in field.split('_'))