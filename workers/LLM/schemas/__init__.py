#!/usr/bin/env python3
# workers/LLM/schemas/__init__.py
"""
Загрузчик схем документов.
Использует DocumentType enum из shared.models.file.enums.
"""

from pathlib import Path
from typing import Optional
from shared.models.file.enums import DocumentType
from .base import BaseSchema
from .generic import GenericSchema

_schema_cache: dict[str, BaseSchema] = {}
SCHEMAS_DIR = Path(__file__).parent


def get_schema_for_type(doc_type: str) -> Optional[BaseSchema]:
    """
    Возвращает схему для типа документа.

    Args:
        doc_type: Тип документа (значение из DocumentType enum)

    Returns:
        BaseSchema или None если схема не найдена
    """
    # Нормализуем через enum для консистентности
    parsed = DocumentType.safe_parse(doc_type)
    canonical_type = parsed.value if parsed else doc_type

    if canonical_type in _schema_cache:
        return _schema_cache[canonical_type]

    schema_file = SCHEMAS_DIR / f"{canonical_type}.json"

    if not schema_file.exists():
        fallback_file = SCHEMAS_DIR / "unknown.json"
        if fallback_file.exists():
            schema_file = fallback_file
        else:
            return None

    schema = GenericSchema(schema_file)
    _schema_cache[canonical_type] = schema
    return schema


def reload_schemas():
    """Перезагружает кэш схем (для разработки)."""
    global _schema_cache
    _schema_cache = {}


def list_available_schemas() -> list[str]:
    """Возвращает список доступных типов схем."""
    return [f.stem for f in SCHEMAS_DIR.glob("*.json") if f.stem != "__init__"]