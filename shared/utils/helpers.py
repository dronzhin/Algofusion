# shared/utils/helpers.py
"""
Вспомогательные функции для всех модулей.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Union
from shared.utils.logger import setup_logger

logger = setup_logger("shared.utils.helpers")


def format_file_size(size_bytes: int, precision: int = 1) -> str:
    """
    Форматирование размера файла в человекочитаемый формат.

    Args:
        size_bytes: Размер в байтах
        precision: Количество знаков после запятой (по умолчанию 1)

    Returns:
        Строка в формате "1.5 MB", "250 KB" и т.д.
    """
    if size_bytes is None or size_bytes == 0:
        return "0 B"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f"{int(size_bytes)} {unit}"
            return f"{size_bytes:.{precision}f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.{precision}f} PB"


def format_datetime(dt: Union[datetime, str, float, int], format_str: str = "%d.%m.%Y %H:%M") -> str:
    """
    Форматирование даты/времени из разных форматов.

    Args:
        dt: datetime, ISO-строка или timestamp
        format_str: Формат вывода (по умолчанию "%d.%m.%Y %H:%M")

    Returns:
        Отформатированная строка даты
    """
    if dt is None or dt == "—":
        return "—"

    try:
        if isinstance(dt, str):
            # ISO формат: 2026-03-27T14:41:06.968164+00:00
            if "T" in dt:
                dt_str = dt.split("+")[0].split(".")[0]
                dt = datetime.fromisoformat(dt_str)
            else:
                dt = datetime.fromisoformat(dt)
        elif isinstance(dt, (int, float)):
            # Timestamp
            dt = datetime.fromtimestamp(dt, tz=timezone.utc)

        # Если datetime без таймзоны — считаем UTC
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.strftime(format_str)

    except Exception as e:
        logger.debug(f"Ошибка форматирования даты: {e}")
        # Возвращаем как есть, но короче
        if isinstance(dt, str) and len(dt) >= 19:
            return dt[:19].replace("T", " ")
        return str(dt)


def safe_mkdir(path: Union[str, Path], mode: int = 0o755) -> Path:
    """Безопасное создание директории с правильными правами."""
    path = Path(path)
    try:
        old_umask = os.umask(0o022)
        try:
            path.mkdir(parents=True, exist_ok=True, mode=mode)
            os.chmod(path, mode)
            logger.debug(f"Директория создана: {path} (права: {oct(mode)})")
            return path
        finally:
            os.umask(old_umask)
    except PermissionError as e:
        logger.error(f"Ошибка прав доступа при создании {path}: {e}")
        raise
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