#!/usr/bin/env python3
# workers/LLM/schemas/generic.py
"""
Универсальная схема, загружаемая из JSON-файла.
"""

from typing import Dict, Any
from jsonschema import validate, ValidationError, Draft7Validator

from .base import BaseSchema


class GenericSchema(BaseSchema):
    """Схема, загружаемая из JSON-файла."""
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Валидация через jsonschema."""
        schema = self.json_schema
        if not schema:
            return True
        try:
            validate(instance=data, schema=schema, cls=Draft7Validator)
            return True
        except ValidationError as e:
            from shared.utils.logger import setup_logger
            logger = setup_logger("workers.llm.schemas")
            logger.warning(f"⚠️ Валидация не прошла для {self.document_type}: {e.message}")
            return False