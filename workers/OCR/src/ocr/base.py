# workers/ocr/src/ocr/base.py
"""Базовый класс для всех OCR движков."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class OCRResult:
    """Результат OCR обработки."""
    success: bool
    text: str
    confidence: float = 0.0
    duration: float = 0.0
    engine: str = ""
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseOCREngine(ABC):
    """Базовый класс для OCR движков."""

    name: str = "base"
    description: str = "Базовый OCR движок"
    version: str = "1.0.0"

    supported_languages: set = {"rus", "eng"}
    supported_formats: set = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**self.get_default_config(), **(config or {})}

    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Конфигурация по умолчанию."""
        pass

    @abstractmethod
    def process(self, input_path: Path, output_path: Path = None) -> OCRResult:
        """Обработка файла."""
        pass

    def validate_input(self, input_path: Path) -> None:
        """Валидация входного файла."""
        if not input_path.exists():
            raise FileNotFoundError(f"Файл не найден: {input_path}")

        if not input_path.is_file():
            raise ValueError(f"Это не файл: {input_path}")

        suffix = input_path.suffix.lower()
        if suffix not in self.supported_formats:
            raise ValueError(
                f"Неподдерживаемый формат: {suffix}. "
                f"Поддерживаемые: {self.supported_formats}"
            )

    def validate_language(self, lang: str) -> bool:
        """Проверка поддержки языка."""
        lang_codes = set(lang.split("+"))
        return all(code in self.supported_languages for code in lang_codes)

    def get_info(self) -> Dict[str, Any]:
        """Информация о движке."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "config": self.config,
            "supported_languages": list(self.supported_languages),
            "supported_formats": list(self.supported_formats)
        }