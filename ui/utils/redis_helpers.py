"""
Утилиты для работы с Redis в UI.
Централизует паттерны получения и обновления данных.
"""

from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING
from shared.utils.logger import setup_logger

# Для типизации без циклических импортов
if TYPE_CHECKING:
    from core.services.redis_client import RedisClient

logger = setup_logger("ui.utils.redis_helpers")


def safe_get_all_files(
        redis_client: Union['RedisClient', List[Dict[str, Any]]],
        default: Optional[List] = None
) -> List[Dict[str, Any]]:
    """
    Безопасное получение списка файлов из Redis.

    Args:
        redis_client: RedisClient ИЛИ уже готовый список файлов (для гибкости)
        default: Значение по умолчанию при ошибке

    Returns:
        List[Dict]: Список файлов или пустой список
    """
    # ← Защитная проверка: если передали список — возвращаем его
    if isinstance(redis_client, list):
        return redis_client

    try:
        # Проверяем, что у объекта есть нужный метод
        if not hasattr(redis_client, 'get_all_files'):
            logger.warning(f"Объект не имеет метода get_all_files: {type(redis_client)}")
            return default or []

        result = redis_client.get_all_files()
        return result if result is not None else []

    except AttributeError as e:
        logger.error(f"AttributeError при получении файлов: {e}")
        return default or []
    except Exception as e:
        logger.error(f"Ошибка получения файлов: {e}", exc_info=True)
        return default or []


def safe_get_file_status(
        redis_client: 'RedisClient',
        file_id: str
) -> Optional[Dict[str, Any]]:
    """Безопасное получение статуса файла."""
    try:
        if not hasattr(redis_client, 'get_file_status'):
            logger.warning(f"Объект не имеет метода get_file_status: {type(redis_client)}")
            return None
        return redis_client.get_file_status(file_id)
    except Exception as e:
        logger.error(f"Ошибка получения статуса файла {file_id}: {e}")
        return None


def safe_update_file_status(
        redis_client: 'RedisClient',
        file_id: str,
        updates: Dict[str, Any]
) -> bool:
    """
    Безопасное обновление статуса файла с сохранением существующих данных.
    """
    try:
        if not hasattr(redis_client, 'get_file_status') or not hasattr(redis_client, 'set_file_status'):
            logger.warning(f"Объект не имеет нужных методов: {type(redis_client)}")
            return False

        existing = redis_client.get_file_status(file_id) or {}
        existing.update(updates)
        return redis_client.set_file_status(file_id, existing)
    except Exception as e:
        logger.error(f"Ошибка обновления статуса файла {file_id}: {e}")
        return False


def push_job_to_queue(
        redis_client: 'RedisClient',
        queue_name: str,
        job_payload: str,
        priority: int = 0
) -> bool:
    """
    Безопасная отправка задачи в очередь.
    """
    try:
        if not hasattr(redis_client, 'push_to_queue'):
            logger.warning(f"Объект не имеет метода push_to_queue: {type(redis_client)}")
            return False

        result = redis_client.push_to_queue(queue_name, job_payload, priority)
        return result > 0
    except Exception as e:
        logger.error(f"Ошибка отправки задачи в очередь {queue_name}: {e}")
        return False


def calculate_file_stats(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Расчёт статистики по списку файлов.

    Returns:
        Dict: Метрики для stats_panel
    """
    total = len(files)
    if total == 0:
        return {
            "total": 0,
            "completed": 0,
            "processing": 0,
            "failed": 0,
            "exported": 0,
            "success_rate": "0%"
        }

    statuses = [f.get("status", "unknown") for f in files]

    return {
        "total": total,
        "completed": statuses.count("completed"),
        "processing": statuses.count("processing"),
        "failed": statuses.count("failed"),
        "exported": statuses.count("exported"),
        "success_rate": f"{(statuses.count('completed') / total * 100):.1f}%"
    }