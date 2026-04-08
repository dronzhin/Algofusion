# shared/utils/helpers.py
"""
Вспомогательные функции для всех модулей.
Единая точка входа для форматирования, работы с путями и Redis.
"""

import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Union, Optional, TYPE_CHECKING

from shared.utils.logger import setup_logger

# Для типизации без циклических импортов
if TYPE_CHECKING:
    from core.services.redis_client import RedisClient
    from shared.models.file import FileJob

logger = setup_logger("shared.utils.helpers")

# ============================================================================
# 🔹 Константы ключей Redis
# ============================================================================
FILE_STATUS_KEY = "file:status:{file_id}"
FILE_JOB_KEY = "file:job:{file_id}"

__all__ = [
    # Форматирование
    "format_file_size",
    "format_datetime",
    "truncate_string",
    # Файловая система
    "safe_mkdir",
    # Утилиты
    "calculate_progress",
    "normalize_string_for_parsing",
    # Redis helpers
    "update_file_in_redis",
    "get_file_job_from_redis",
    "delete_file_from_redis",
    "FILE_STATUS_KEY",
    "FILE_JOB_KEY",
]


# ============================================================================
# 🔹 Форматирование и отображение
# ============================================================================

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


def format_datetime(dt: Union[datetime, str, float, int, None],
                    format_str: str = "%d.%m.%Y %H:%M") -> str:
    """
    Форматирование даты/времени из разных форматов.

    Args:
        dt: datetime, ISO-строка, timestamp или None
        format_str: Формат вывода (по умолчанию "%d.%m.%Y %H:%M")

    Returns:
        Отформатированная строка даты или "—" при ошибке
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


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Обрезка строки с суффиксом."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


# ============================================================================
# 🔹 Работа с файловой системой
# ============================================================================

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


# ============================================================================
# 🔹 Утилиты
# ============================================================================

def calculate_progress(completed: int, total: int) -> float:
    """Расчёт прогресса в процентах."""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 2)


def normalize_string_for_parsing(value: Optional[str]) -> Optional[str]:
    """
    Нормализация строки для безопасного парсинга.

    Приводит к нижнему регистру, заменяёт ё→е,
    пробелы/дефисы/подчёркивания → единый "_".

    Args:
        value: Исходная строка

    Returns:
        Нормализованная строка или None
    """
    if not value or not value.strip():
        return None

    normalized = value.strip().lower().replace("ё", "е")
    # Пробелы, дефисы, табуляции, переносы → "_"
    normalized = re.sub(r"[\s\-_\t\n\r]+", "_", normalized)
    # Убираем множественные "__" и крайние "_"
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    return normalized if normalized else None


# ============================================================================
# 🔹 Redis Helpers — работа с FileJob в Redis
# ============================================================================

def update_file_in_redis(
        redis_client: Union["RedisClient", object],
        job: "FileJob",
        key_pattern: str = FILE_JOB_KEY
) -> bool:
    """
    Обновляет состояние FileJob в Redis.

    Args:
        redis_client: Экземпляр RedisClient или объект с методом set()
        job: FileJob для сохранения
        key_pattern: Шаблон ключа (по умолчанию "file:job:{file_id}")

    Returns:
        bool: True если успешно, False при ошибке
    """
    try:
        # Проверка на наличие метода (защита от моков в тестах)
        if not hasattr(redis_client, "set"):
            logger.warning(f"RedisClient не имеет метода set: {type(redis_client)}")
            return False

        key = key_pattern.format(file_id=job.file_id)
        payload = job.to_payload()  # Сериализация в JSON-строку

        success = redis_client.set(key, payload)
        if success:
            logger.debug(f"✅ Job обновлён в Redis: {key}")
        else:
            logger.warning(f"⚠️ Redis.set вернул False для {key}")
        return success

    except AttributeError as e:
        logger.error(f"❌ AttributeError при обновлении job: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка обновления job в Redis: {e}", exc_info=True)
        return False


def get_file_job_from_redis(
        redis_client: Union["RedisClient", object],
        file_id: str,
        job_class: type = None,  # type: ignore
        key_pattern: str = FILE_JOB_KEY
) -> Optional["FileJob"]:
    """
    Загружает FileJob из Redis по ID.

    Args:
        redis_client: Экземпляр RedisClient или объект с методом get()
        file_id: ID файла
        job_class: Класс для десериализации (по умолчанию FileJob)
        key_pattern: Шаблон ключа

    Returns:
        Optional[FileJob]: Объект или None при ошибке/отсутствии
    """
    if job_class is None:
        from shared.models.file import FileJob
        job_class = FileJob

    try:
        if not hasattr(redis_client, "get"):
            logger.warning(f"RedisClient не имеет метода get: {type(redis_client)}")
            return None

        key = key_pattern.format(file_id=file_id)
        payload = redis_client.get(key)

        if not payload:
            logger.debug(f"⚠️ Job не найден в Redis: {key}")
            return None

        # Используем безопасный парсинг
        job, error = job_class.from_payload_safe(payload)
        if error:
            logger.error(f"❌ Ошибка парсинга job из Redis: {error}")
            return None

        return job

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки job из Redis: {e}", exc_info=True)
        return None


def delete_file_from_redis(
        redis_client: Union["RedisClient", object],
        file_id: str,
        key_pattern: str = FILE_JOB_KEY
) -> bool:
    """
    Удаляет запись о файле из Redis.

    Args:
        redis_client: Экземпляр RedisClient или объект с методом delete()
        file_id: ID файла
        key_pattern: Шаблон ключа

    Returns:
        bool: True если успешно, False при ошибке
    """
    try:
        if not hasattr(redis_client, "delete"):
            logger.warning(f"RedisClient не имеет метода delete: {type(redis_client)}")
            return False

        key = key_pattern.format(file_id=file_id)
        result = redis_client.delete(key)
        logger.debug(f"🗑️ Удалено из Redis: {key} (result={result})")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка удаления из Redis: {e}", exc_info=True)
        return False