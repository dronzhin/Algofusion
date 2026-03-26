from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.logger import get_logger
from src.models.file import FileJob


class BaseModule(ABC):
    name: str = "base"
    description: str = "Base processing module"
    version: str = "1.0.0"
    supported_file_types: set = set()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger(f"module.{self.name}")

    @abstractmethod
    def process(self, job: FileJob) -> bool:
        pass

    def validate_file_type(self, job: FileJob) -> bool:
        if not self.supported_file_types:
            return True
        return job.file_type in self.supported_file_types
