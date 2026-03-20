# core/models.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from enum import Enum


class FileStatus(str, Enum):
    EXPORTED = "🟢 Экспортирован в 1С"
    PROCESSING = "🟡 Обработка"
    NEEDS_FIX = "🔴 Требует правки"
    NEW = "🔵 Новый"
    FIXED = "🟣 Поправлен"


class FileRecord(BaseModel):
    """Модель записи файла"""
    date: str  # "DD.MM.YYYY HH:MM"
    filename: str
    status: FileStatus
    file_type: str
    metrics: str  # "95%"
    export_1c: str  # "✅", "⏳", etc.

    @property
    def metric_value(self) -> Optional[int]:
        try:
            return int(self.metrics.replace('%', ''))
        except:
            return None

    @property
    def parsed_date(self) -> Optional[datetime]:
        try:
            return datetime.strptime(self.date.split()[0], "%d.%m.%Y")
        except:
            return None

    class Config:
        use_enum_values = True