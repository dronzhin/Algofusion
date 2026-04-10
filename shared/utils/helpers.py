# shared/utils/helpers.py
"""
Вспомогательные функции для всех модулей.
Единая точка входа для форматирования, работы с путями и Redis.
"""

import os
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Union, Optional, Dict, Any, List, TYPE_CHECKING

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
FILE_FINGERPRINT_INDEX = "file:fp:{fingerprint}"  # Индекс fingerprint → file_id

__all__ = [
    # Форматирование
    "format_file_size",
    "format_datetime",
    "truncate_string",
    # Файловая система + fingerprint
    "safe_mkdir",
    "get_file_fingerprint",
    "validate_file_exists",
    "get_safe_file_path",
    # Утилиты
    "calculate_progress",
    "normalize_string_for_parsing",
    "is_job_terminal_or_active",
    # Проверка дубликатов
    "is_file_already_processed",
    "is_file_already_processed_by_fingerprint",
    "update_fingerprint_index",
    "cleanup_orphaned_jobs",
    # Redis helpers
    "update_file_in_redis",
    "get_file_job_from_redis",
    "delete_file_from_redis",
    # Константы
    "FILE_STATUS_KEY",
    "FILE_JOB_KEY",
    "FILE_FINGERPRINT_INDEX",
]


# ============================================================================
# 🔹 Форматирование и отображение
# ============================================================================

def format_file_size(size_bytes: int, precision: int = 1) -> str:
    """Форматирование размера файла в человекочитаемый формат."""
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
    """Форматирование даты/времени из разных форматов."""
    if dt is None or dt == "—":
        return "—"
    try:
        if isinstance(dt, str):
            if "T" in dt:
                dt_str = dt.split("+")[0].split(".")[0]
                dt = datetime.fromisoformat(dt_str)
            else:
                dt = datetime.fromisoformat(dt)
        elif isinstance(dt, (int, float)):
            dt = datetime.fromtimestamp(dt, tz=timezone.utc)
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime(format_str)
    except Exception as e:
        logger.debug(f"Ошибка форматирования даты: {e}")
        if isinstance(dt, str) and len(dt) >= 19:
            return dt[:19].replace("T", " ")
        return str(dt)


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Обрезка строки с суффиксом."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


# ============================================================================
# 🔹 Работа с файловой системой + Fingerprint (Content-Based)
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


def get_file_fingerprint(filepath: Path, use_content: bool = True) -> Optional[str]:
    """
    Генерирует уникальный отпечаток файла.

    🔹 КЛЮЧЕВОЕ: по умолчанию хэшируем СОДЕРЖИМОЕ файла, а не путь.
    Это гарантирует одинаковый fingerprint после копирования в другую директорию.

    Args:
        filepath: Путь к файлу
        use_content: True → content-based (рекомендуется), False → path+metadata

    Returns:
        str: 16-символьный hex-хэш или None
    """
    if not filepath.exists() or not filepath.is_file():
        return None

    try:
        if use_content:
            # Хэшируем первые 1MB + точный размер файла для баланса скорости и надёжности
            hasher = hashlib.sha256()
            file_size = filepath.stat().st_size

            with open(filepath, 'rb') as f:
                chunk = f.read(1024 * 1024)  # 1 MB
                hasher.update(chunk)

            hasher.update(str(file_size).encode())
            return hasher.hexdigest()[:16]
        else:
            # Legacy: путь + mtime + size
            stat = filepath.stat()
            raw = f"{filepath.resolve()}:{stat.st_mtime}:{stat.st_size}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    except (OSError, PermissionError, FileNotFoundError, IOError) as e:
        logger.debug(f"Не удалось получить fingerprint для {filepath}: {e}")
        return None


def validate_file_exists(file_id: str, original_filename: str, base_dir: Union[str, Path] = "/shared/files") -> bool:
    """Проверяет существование оригинального файла на диске."""
    try:
        base = Path(base_dir)
        file_path = base / file_id / "original" / original_filename
        return file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0
    except (OSError, PermissionError, ValueError):
        return False


def get_safe_file_path(file_id: str, original_filename: str, base_dir: Union[str, Path] = "/shared/files") -> Optional[
    Path]:
    """Возвращает безопасный Path к файлу или None, если файл не существует."""
    try:
        if "/" in original_filename or "\\" in original_filename:
            logger.warning(f"Подозрительное имя файла: {original_filename}")
            return None

        base = Path(base_dir).resolve()
        file_path = (base / file_id / "original" / original_filename).resolve()

        if not str(file_path).startswith(str(base)):
            logger.warning(f"Попытка доступа за пределы base_dir: {file_path}")
            return None

        return file_path if file_path.exists() else None
    except Exception as e:
        logger.debug(f"Ошибка получения safe path для {file_id}/{original_filename}: {e}")
        return None


# ============================================================================
# 🔹 Утилиты и проверка статусов
# ============================================================================

def calculate_progress(completed: int, total: int) -> float:
    """Расчёт прогресса в процентах."""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 2)


def normalize_string_for_parsing(value: Optional[str]) -> Optional[str]:
    """Нормализация строки для безопасного парсинга."""
    if not value or not value.strip():
        return None
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[\s\-_\t\n\r]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized if normalized else None


def is_job_terminal_or_active(job_data: Dict[str, Any]

) -> bool:
    """Определяет, требует ли джоб повторной обработки."""
    status = job_data.get("status", "unknown")
    retry_count = job_data.get("retry_count", 0)
    max_retries = job_data.get("max_retries", 3)

    if status in ("completed", "exported"):
        return True
    if status == "failed" and retry_count >= max_retries:
        return True
    if status in ("uploaded", "processing"):
        return True
    if status == "failed" and retry_count < max_retries:
        return True
    return False


# ============================================================================
# 🔹 Проверка дубликатов и индексы
# ============================================================================

def is_file_already_processed_by_fingerprint(
        fingerprint: str,
        redis_client: Any
) -> bool:
    """
    Проверяет наличие файла по его fingerprint в индексе Redis.
    Быстрая и надёжная проверка, не зависящая от путей.
    """
    if not fingerprint or not redis_client:
        return False

    try:
        if hasattr(redis_client, 'get'):
            key = FILE_FINGERPRINT_INDEX.format(fingerprint=fingerprint)
            existing_file_id = redis_client.get(key)
            if existing_file_id:
                if hasattr(redis_client, 'get_file_status'):
                    job_data = redis_client.get_file_status(existing_file_id)
                    if job_data:
                        return is_job_terminal_or_active(job_data)
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки по fingerprint {fingerprint}: {e}")
        return False  # fail-open


def is_file_already_processed(
        filepath: Path,
        redis_client: Any,
        base_dir: Union[str, Path] = "/shared/files"
) -> bool:
    """Обёртка для обратной совместимости. Вычисляет fingerprint и проверяет индекс."""
    fingerprint = get_file_fingerprint(filepath, use_content=True)
    if fingerprint:
        return is_file_already_processed_by_fingerprint(fingerprint, redis_client)
    return False  # Если не удалось вычислить fingerprint — разрешаем обработку


def update_fingerprint_index(
        redis_client: Any,
        file_id: str,
        fingerprint: str,
        ttl: int = 30 * 24 * 3600  # 30 дней
) -> bool:
    """Создаёт/обновляет индекс fingerprint → file_id в Redis."""
    try:
        if not hasattr(redis_client, "set"):
            return False
        key = FILE_FINGERPRINT_INDEX.format(fingerprint=fingerprint)
        if hasattr(redis_client, "client") and hasattr(redis_client.client, "setex"):
            redis_client.client.setex(key, ttl, file_id)
        else:
            redis_client.set(key, file_id)
        logger.debug(f"🔗 Индекс fingerprint обновлён: {fingerprint} → {file_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка обновления индекса fingerprint: {e}")
        return False


def cleanup_orphaned_jobs(
        redis_client: Any,
        base_dir: Union[str, Path] = "/shared/files",
        min_age_hours: int = 1,
        batch_limit: int = 100
) -> Dict[str, int]:
    """Удаляет из Redis джобы, ссылающиеся на несуществующие файлы."""
    stats = {"cleaned": 0, "skipped": 0, "errors": 0}
    try:
        if not hasattr(redis_client, 'get_all_files'):
            return stats

        all_files = redis_client.get_all_files()
        logger.info(f"🔍 Начинаю очистку: проверю {len(all_files)} джобов")

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)
        safe_statuses = {"completed", "exported", "failed"}

        for file_data in all_files[:batch_limit]:
            file_id = file_data.get("file_id")
            original_filename = file_data.get("original_filename", "")
            status = file_data.get("status", "unknown")
            created_at = file_data.get("created_at")

            if status not in safe_statuses:
                stats["skipped"] += 1
                continue

            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if created_at > cutoff_time:
                        stats["skipped"] += 1
                        continue
                except Exception:
                    pass

            if validate_file_exists(file_id, original_filename, base_dir):
                stats["skipped"] += 1
                continue

            try:
                if hasattr(redis_client, 'delete_file_status'):
                    redis_client.delete_file_status(file_id)
                fingerprint = file_data.get("metadata", {}).get("file_fingerprint")
                if fingerprint and hasattr(redis_client, 'delete'):
                    fp_key = FILE_FINGERPRINT_INDEX.format(fingerprint=fingerprint)
                    redis_client.delete(fp_key)
                stats["cleaned"] += 1
                logger.info(f"🗑️ Удалён осиротевший джоб: {file_id}")
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"❌ Ошибка удаления джоба {file_id}: {e}")

        try:
            from ui.cache import CacheManager
            CacheManager.clear_data_cache()
        except ImportError:
            pass

        logger.info(f"✅ Очистка завершена: {stats['cleaned']} удалено, {stats['skipped']} пропущено")
        return stats
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cleanup_orphaned_jobs: {e}", exc_info=True)
        return {"cleaned": 0, "skipped": 0, "errors": 1}


# ============================================================================
# 🔹 Redis Helpers
# ============================================================================

def update_file_in_redis(redis_client: Union["RedisClient", object], job: "FileJob",
                         key_pattern: str = FILE_JOB_KEY) -> bool:
    try:
        if not hasattr(redis_client, "set"): return False
        key = key_pattern.format(file_id=job.file_id)
        success = redis_client.set(key, job.to_payload())
        if success: logger.debug(f"✅ Job обновлён в Redis: {key}")
        return success
    except Exception as e:
        logger.error(f"❌ Ошибка обновления job в Redis: {e}", exc_info=True)
        return False


def get_file_job_from_redis(redis_client: Union["RedisClient", object], file_id: str, job_class: type = None,
                            key_pattern: str = FILE_JOB_KEY) -> Optional["FileJob"]:
    if job_class is None:
        from shared.models.file import FileJob
        job_class = FileJob
    try:
        if not hasattr(redis_client, "get"): return None
        key = key_pattern.format(file_id=file_id)
        payload = redis_client.get(key)
        if not payload: return None
        job, error = job_class.from_payload_safe(payload)
        return None if error else job
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки job из Redis: {e}", exc_info=True)
        return None


def delete_file_from_redis(redis_client: Union["RedisClient", object], file_id: str,
                           key_pattern: str = FILE_JOB_KEY) -> bool:
    try:
        if not hasattr(redis_client, "delete"): return False
        key = key_pattern.format(file_id=file_id)
        result = redis_client.delete(key)
        logger.debug(f"🗑️ Удалено из Redis: {key}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка удаления из Redis: {e}", exc_info=True)
        return False