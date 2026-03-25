# ui/utils/redis_helpers.py
"""
Утилиты для работы с Redis в UI.
Централизует паттерны получения и обновления данных.
"""

from typing import Optional, Dict, Any, List
from shared.utils.logger import setup_logger

logger = setup_logger("ui.utils.redis_helpers")


def safe_get_all_files(redis_client, default: List = None) -> List[Dict[str, Any]]:
    """
    Безопасное получение списка файлов из Redis.

    Args:
        redis_client: Экземпляр RedisClient
        default: Значение по умолчанию при ошибке

    Returns:
        Список файлов или пустой список
    """
    try:
        return redis_client.get_all_files() or []
    except Exception as e:
        logger.error(f"Ошибка получения файлов: {e}")
        return default or []


def safe_get_file_status(redis_client, file_id: str) -> Optional[Dict[str, Any]]:
    """Безопасное получение статуса файла."""
    try:
        return redis_client.get_file_status(file_id)
    except Exception as e:
        logger.error(f"Ошибка получения статуса файла {file_id}: {e}")
        return None


def safe_update_file_status(redis_client, file_id: str, updates: Dict[str, Any]) -> bool:
    """
    Безопасное обновление статуса файла с сохранением существующих данных.

    Args:
        redis_client: Экземпляр RedisClient
        file_id: ID файла
        updates: Словарь с полями для обновления

    Returns:
        True если обновление успешно
    """
    try:
        existing = redis_client.get_file_status(file_id) or {}
        existing.update(updates)
        return redis_client.set_file_status(file_id, existing)
    except Exception as e:
        logger.error(f"Ошибка обновления статуса файла {file_id}: {e}")
        return False


def push_job_to_queue(redis_client, queue_name: str, job_payload: str, priority: int = 0) -> bool:
    """
    Безопасная отправка задачи в очередь.

    Args:
        redis_client: Экземпляр RedisClient
        queue_name: Имя очереди (без префикса)
        job_payload: JSON-строка с данными задачи
        priority: Приоритет (0 = обычный)

    Returns:
        True если задача отправлена
    """
    try:
        result = redis_client.push_to_queue(queue_name, job_payload, priority)
        return result > 0
    except Exception as e:
        logger.error(f"Ошибка отправки задачи в очередь {queue_name}: {e}")
        return False


def calculate_file_stats(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Расчёт статистики по списку файлов.

    Returns:
        Словарь с метриками для stats_panel
    """
    total = len(files)
    if total == 0:
        return {"total": 0, "completed": 0, "processing": 0, "failed": 0, "exported": 0, "success_rate": "0%"}

    statuses = [f.get("status", "unknown") for f in files]

    return {
        "total": total,
        "completed": statuses.count("completed"),
        "processing": statuses.count("processing"),
        "failed": statuses.count("failed"),
        "exported": statuses.count("exported"),
        "success_rate": f"{(statuses.count('completed') / total * 100):.1f}%"
    }