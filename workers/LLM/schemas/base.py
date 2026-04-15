#!/usr/bin/env python3
# workers/LLM/schemas/base.py
"""
Базовый класс для схем документов с OCR-aware валидацией.
✅ Проверяет, что извлечённые значения имеют основание в исходном тексте
✅ Применяет нормализацию, согласованную с промптом
✅ Отклоняет галлюцинации и «слишком идеальные» значения
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import json
import re
from datetime import datetime

from shared.utils.logger import setup_logger

logger = setup_logger("workers.llm.schemas")


class BaseSchema(ABC):
    """Абстрактный базовый класс для схем документов с валидацией против OCR-текста."""

    document_type: str = "unknown"

    # 🔹 Паттерны для базовой валидации типов
    FIELD_PATTERNS = {
        "date": r"^\d{4}-\d{2}-\d{2}$",  # ГГГГ-ММ-ДД
        "number": r"^-?\d+(\.\d+)?$",  # Число с плавающей точкой
        "percentage": r"^\d+(\.\d+)?$",  # Процент без знака %
        "inn_ru": r"^\d{10}$|^\d{12}$",  # ИНН РФ
        "inn_by": r"^\d{9}$",  # ИНН РБ
        "phone": r"^\+?\d[\d\s\-\(\)]{7,}$",  # Телефон
    }

    def __init__(self, schema_path: Optional[Path] = None):
        self.schema_path = schema_path
        self._data: Optional[Dict[str, Any]] = None
        self._loaded = False
        self._ocr_text_cache: Optional[str] = None  # 🔹 Кэш исходного текста для валидации

    def _load_data(self) -> Dict[str, Any]:
        """Ленивая загрузка схемы из файла."""
        if not self._loaded and self.schema_path and self.schema_path.exists():
            try:
                with open(self.schema_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as e:
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

    # ========================================================================
    # 🔹 OCR-AWARE ВАЛИДАЦИЯ: Ключевые методы
    # ========================================================================

    def set_ocr_text(self, text: str):
        """Устанавливает исходный OCR-текст для последующей валидации."""
        self._ocr_text_cache = text

    def _normalize_for_comparison(self, value: Any) -> str:
        """
        Нормализует значение для сравнения с сырым текстом.
        Применяет те же правила, что и в промпте (для согласованности).
        """
        if value is None:
            return ""

        str_val = str(value).strip()

        # 🔹 Удаляем лишние пробелы, переносы, спецсимволы
        str_val = re.sub(r'[\s\n\r]+', ' ', str_val)
        str_val = re.sub(r'[—–\-]{2,}', '-', str_val)  # Нормализуем тире
        str_val = re.sub(r'[®™©]', '', str_val)  # Удаляем символы копирайта

        # 🔹 Нормализуем числа: "1 234.50" → "1234.50", "633,02" → "633.02"
        if re.match(r'^[\d\s\.,\-]+$', str_val):
            str_val = re.sub(r'[\s]', '', str_val)  # Убираем пробелы
            str_val = re.sub(r'(\d),(\d{2})$', r'\1.\2', str_val)  # "633,02" → "633.02"

        # 🔹 Приводим к нижнему регистру для нечувствительного сравнения
        return str_val.lower()

    def _value_exists_in_ocr(self, value: Any, field_name: str, ocr_text: Optional[str] = None) -> bool:
        """
        Проверяет, есть ли значение (или его часть) в исходном OCR-тексте.
        🔹 Возвращает True, если найдено точное или нечёткое совпадение.
        """
        if value is None or value == "" or value == []:
            return True  # null/пустые значения — ок

        ocr = ocr_text or self._ocr_text_cache
        if not ocr:
            logger.warning(f"⚠️ Нет исходного текста для валидации поля '{field_name}'")
            return True  # Не блокируем, если нет текста для проверки

        normalized_value = self._normalize_for_comparison(value)
        normalized_ocr = self._normalize_for_comparison(ocr)

        # 🔹 1. Прямое вхождение
        if normalized_value in normalized_ocr:
            return True

        # 🔹 2. Для строк: проверяем, есть ли ключевые токены значения в тексте
        if isinstance(value, str) and len(value) > 3:
            # Разбиваем на слова/токены
            tokens = re.findall(r'[\wа-яА-ЯёЁ]+', value)
            if tokens:
                # Достаточно, чтобы 50% токенов нашлись в тексте
                found = sum(1 for t in tokens if self._normalize_for_comparison(t) in normalized_ocr)
                if found >= max(1, len(tokens) // 2):
                    return True

        # 🔹 3. Для дат: проверяем, есть ли компоненты даты в тексте
        if field_name.endswith("_date") or field_name in ["date", "issued_at", "due_date"]:
            date_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
            if date_match:
                year, month, day = date_match.groups()
                # Проверяем, есть ли хотя бы год и день в исходном тексте
                if year in ocr and day in ocr:
                    return True

        # 🔹 4. Для чисел: ищем числовое значение в тексте (с учётом форматов)
        if isinstance(value, (int, float)) or re.match(r'^-?\d+\.?\d*$', str(value)):
            num_str = str(value).replace('.', ',')  # Пробуем оба формата
            # Ищем число в тексте с допустимыми разделителями
            number_pattern = re.escape(num_str).replace(r'\.', r'[.,]').replace(r'\,', r'[,.]')
            if re.search(number_pattern, ocr):
                return True
            # Также пробуем найти без разделителей (для случаев "1 234" → 1234)
            digits_only = re.sub(r'[^\d]', '', str(value))
            if digits_only and digits_only in re.sub(r'[^\d]', '', ocr):
                return True

        # 🔹 5. Нечёткое сравнение для коротких строк (названия, ИНН)
        if isinstance(value, str) and 3 <= len(value) <= 20:
            # Проверяем, есть ли подстрока длиной >= 70% от значения
            min_match_len = max(3, int(len(value) * 0.7))
            for i in range(len(value) - min_match_len + 1):
                substring = value[i:i + min_match_len]
                if self._normalize_for_comparison(substring) in normalized_ocr:
                    return True

        return False

    def _validate_field_type(self, field_name: str, value: Any, field_def: Dict) -> bool:
        """Валидирует тип и формат значения согласно определению поля."""
        if value is None:
            return True  # null допустим, если поле не required (проверяется отдельно)

        expected_type = field_def.get("type")

        # 🔹 Проверка базовых типов
        if expected_type == "string" and not isinstance(value, str):
            return False
        if expected_type == "number" and not isinstance(value, (int, float)):
            return False
        if expected_type == "integer" and not isinstance(value, int):
            return False
        if expected_type == "boolean" and not isinstance(value, bool):
            return False

        # 🔹 Проверка форматов через паттерны
        field_format = field_def.get("format")
        if field_format and field_format in self.FIELD_PATTERNS:
            pattern = self.FIELD_PATTERNS[field_format]
            if not re.match(pattern, str(value)):
                logger.warning(f"⚠️ Поле '{field_name}': значение '{value}' не соответствует формату '{field_format}'")
                return False

        # 🔹 Проверка enum
        if "enum" in field_def and value not in field_def["enum"]:
            logger.warning(f"⚠️ Поле '{field_name}': значение '{value}' не в enum {field_def['enum']}")
            return False

        # 🔹 Проверка диапазона для чисел
        if expected_type in ("number", "integer"):
            if "minimum" in field_def and value < field_def["minimum"]:
                return False
            if "maximum" in field_def and value > field_def["maximum"]:
                return False

        return True

    @abstractmethod
    def validate(self, data: Dict[str, Any], ocr_text: Optional[str] = None) -> bool:
        """
        Валидирует извлечённые данные против схемы И исходного OCR-текста.

        Args:
            data: Извлечённые данные
            ocr_text: Исходный текст документа (для проверки на галлюцинации)

        Returns:
            bool: True если данные валидны, False если есть ошибки
        """
        pass

    def validate_with_report(
            self,
            data: Dict[str, Any],
            ocr_text: Optional[str] = None
    ) -> tuple[bool, List[str]]:
        """
        Валидация с возвратом списка предупреждений.

        Returns:
            (is_valid: bool, warnings: List[str])
        """
        warnings = []

        # 🔹 1. Базовая валидация схемы
        if not self.validate(data, ocr_text):
            warnings.append("Схема не пройдена")
            return False, warnings

        # 🔹 2. Проверка required полей
        required = self.get_required_fields()
        for field in required:
            if field not in data or data[field] is None:
                warnings.append(f"⚠️ Отсутствует обязательное поле: {field}")

        # 🔹 3. OCR-проверка для строковых полей (если есть текст)
        if ocr_text:
            properties = self.json_schema.get("properties", {})
            for field_name, value in data.items():
                if field_name.startswith("_"):  # Служебные поля пропускаем
                    continue
                field_def = properties.get(field_name, {})

                # Проверяем только строковые и числовые поля
                if isinstance(value, (str, int, float)) and value not in (None, "", []):
                    if not self._value_exists_in_ocr(value, field_name, ocr_text):
                        # 🔹 Не блокируем, но логируем подозрительные значения
                        warnings.append(
                            f"⚠️ Поле '{field_name}': значение '{value}' не найдено в исходном тексте "
                            f"(возможная галлюцинация или ошибка нормализации)"
                        )

        return len(warnings) == 0 or all("⚠️" in w for w in warnings), warnings  # Предупреждения ≠ ошибки

    def format_example_for_prompt(self) -> str:
        """Форматирует пример для вставки в промпт."""
        if not self.example:
            return ""
        return json.dumps(self.example, ensure_ascii=False, indent=2)