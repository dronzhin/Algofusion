#!/usr/bin/env python3
# workers/LLM/schemas/generic.py
"""
Универсальная схема с OCR-aware валидацией.
✅ Проверяет соответствие значений исходному тексту
✅ Отклоняет галлюцинации
✅ Поддерживает jsonschema + кастомные правила
"""

from typing import Dict, Any, Optional, List
from jsonschema import validate, ValidationError, Draft7Validator

from .base import BaseSchema
from shared.utils.logger import setup_logger

logger = setup_logger("workers.llm.schemas")


class GenericSchema(BaseSchema):
    """Схема с полной валидацией: jsonschema + OCR-проверка + кастомные правила."""

    def validate(self, data: Dict[str, Any], ocr_text: Optional[str] = None) -> bool:
        """
        Полная валидация данных:
        1. JSON Schema валидация
        2. Проверка типов и форматов
        3. OCR-проверка: есть ли значения в исходном тексте
        """
        schema = self.json_schema
        if not schema:
            return True  # Нет схемы — не блокируем

        # 🔹 1. Базовая валидация через jsonschema
        try:
            validate(instance=data, schema=schema, cls=Draft7Validator)
        except ValidationError as e:
            logger.warning(f"⚠️ JSON Schema валидация не пройдена: {e.message}")
            return False

        # 🔹 2. Валидация типов и форматов для каждого поля
        properties = schema.get("properties", {})
        for field_name, value in data.items():
            if field_name.startswith("_"):  # Служебные поля
                continue
            if field_name not in properties:
                continue  # Дополнительные поля разрешены (additionalProperties не проверяем строго)

            field_def = properties[field_name]
            if not self._validate_field_type(field_name, value, field_def):
                logger.warning(f"⚠️ Поле '{field_name}': не соответствует типу/формату")
                return False

        # 🔹 3. OCR-проверка: если есть исходный текст, проверяем наличие значений
        if ocr_text:
            self._ocr_text_cache = ocr_text  # Сохраняем для методов базы
            suspicious_fields = []

            for field_name, value in data.items():
                if field_name.startswith("_"):
                    continue
                if value is None or value == "" or value == []:
                    continue  # Пустые значения — ок

                # Проверяем, есть ли значение в тексте
                if not self._value_exists_in_ocr(value, field_name, ocr_text):
                    suspicious_fields.append(field_name)

            # 🔹 Если много подозрительных полей — это красный флаг
            if len(suspicious_fields) > len(data) * 0.3:  # >30% полей не найдены
                logger.warning(
                    f"⚠️ Много полей не найдены в тексте: {suspicious_fields}. "
                    f"Возможна галлюцинация модели."
                )
                return False  # Блокируем, если слишком много несоответствий

            # 🔹 Логируем отдельные подозрительные поля (но не блокируем)
            for field in suspicious_fields:
                logger.debug(f"🔍 Поле '{field}': значение не найдено в тексте (требует проверки)")

        return True

    def validate_strict(self, data: Dict[str, Any], ocr_text: str) -> tuple[bool, List[str]]:
        """
        Строгая валидация: блокирует любые значения, не найденные в тексте.
        Используется для критичных полей (суммы, даты, реквизиты).

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        # 🔹 Базовая валидация
        if not self.validate(data, ocr_text):
            errors.append("Базовая валидация не пройдена")
            return False, errors

        # 🔹 Строгая проверка: каждое значение должно быть в тексте
        properties = self.json_schema.get("properties", {})
        strict_fields = [
            name for name, prop in properties.items()
            if prop.get("x-strict-ocr", False)  # 🔹 Маркер для строгих полей
        ]

        for field_name in strict_fields:
            if field_name not in data:
                continue
            value = data[field_name]
            if value is None or value == "":
                continue

            if not self._value_exists_in_ocr(value, field_name, ocr_text):
                errors.append(
                    f"❌ Строгое поле '{field_name}': значение '{value}' не найдено в исходном тексте"
                )

        return len(errors) == 0, errors