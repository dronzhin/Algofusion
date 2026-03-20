# shared/utils/helpers.py
"""
Вспомогательные функции для всех модулей.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Union
from shared.utils.logger import setup_logger

logger = setup_logger("shared.utils.helpers")


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_datetime(dt: Union[datetime, str], format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Форматирование даты/времени."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    return dt.strftime(format_str)


def safe_mkdir(path: Union[str, Path], mode: int = 0o755) -> Path:
    """Безопасное создание директории."""
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        logger.debug(f"Директория создана: {path}")
        return path
    except Exception as e:
        logger.error(f"Ошибка создания директории {path}: {e}")
        raise


def calculate_progress(completed: int, total: int) -> float:
    """Расчёт прогресса в процентах."""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 2)


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Обрезка строки с суффиксом."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix