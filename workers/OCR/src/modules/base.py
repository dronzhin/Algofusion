# workers/ocr/src/modules/base.py
"""Базовый класс для всех модулей обработки."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from src.models.file import FileJob
from src.logger import get_logger


class BaseModule(ABC):
    """Базовый класс модуля обработки."""

    name: str = "base"
    description: str = "Базовый модуль"
    version: str = "1.0.0"
    supported_file_types: set = set()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger(f"module.{self.name}")

    @abstractmethod
    def process(self, job: FileJob) -> bool:
        """Обработка файла."""
        pass

    def validate_file_type(self, job: FileJob) -> bool:
        """Проверка поддерживает ли модуль этот тип файла."""
        if not self.supported_file_types:
            return True
        return job.file_type in self.supported_file_types

    def get_input_path(self, job: FileJob, from_module: str = None) -> Path:
        """Получить путь к входному файлу."""
        if from_module:
            return job.get_module_output_path(from_module)
        return job.get_original_path()

    def get_output_path(self, job: FileJob) -> Path:
        """Получить путь для результата."""
        return job.get_module_output_path(self.name)

    def prepare_staging(self, job: FileJob) -> Path:
        """Подготовить временную папку."""
        staging_path = job.get_base_path() / "staging" / self.name
        staging_path.mkdir(parents=True, exist_ok=True)
        return staging_path