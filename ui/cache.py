# ui/cache.py
"""
Слой кэширования для Streamlit UI.
Использует @st.cache_data и @st.cache_resource для оптимизации.
"""

import streamlit as st
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
from shared.utils.logger import setup_logger

logger = setup_logger("ui.cache")


# ============================================================================
# STREAMLIT CACHE DECORATORS
# ============================================================================

@st.cache_resource(ttl=3600)  # 1 час
def get_redis_client_cached():
    """
    Кэшированный Redis клиент.
    Использует @st.cache_resource для тяжелых объектов подключения.
    """
    from core.services.redis_client import get_redis_client
    logger.info("Создание нового Redis подключения (кэшировано)")
    return get_redis_client()


@st.cache_data(ttl=60)  # 60 секунд
def get_files_from_redis_cached(redis_client, cache_key: str = "all") -> List[Dict[str, Any]]:
    """
    Кэшированное получение списка файлов из Redis.
    TTL 60 секунд для баланса между актуальностью и производительностью.
    """
    try:
        files = redis_client.get_all_files()
        logger.debug(f"Загружено {len(files)} файлов из Redis (кэш: {cache_key})")
        return files
    except Exception as e:
        logger.error(f"Ошибка получения файлов: {e}")
        return []


@st.cache_data(ttl=300)  # 5 минут
def get_file_stats_cached(redis_client) -> Dict[str, Any]:
    """
    Кэшированная статистика файлов.
    Менее критично к актуальности, поэтому TTL больше.
    """
    try:
        files = redis_client.get_all_files()
        total = len(files)

        statuses = [f.get("status", "unknown") for f in files]
        completed = statuses.count("completed")
        processing = statuses.count("processing")
        failed = statuses.count("failed")
        exported = statuses.count("exported")

        success_rate = f"{(completed / total * 100):.1f}%" if total > 0 else "0%"

        return {
            "total": total,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "exported": exported,
            "success_rate": success_rate
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"total": 0, "completed": 0, "processing": 0, "failed": 0, "exported": 0}


@st.cache_data(ttl=600)  # 10 минут
def get_file_structure_cached(file_service, file_id: str) -> Optional[Dict[str, Any]]:
    """
    Кэшированная структура файлов.
    Изменяется редко, поэтому TTL большой.
    """
    try:
        return file_service.get_file_info(file_id)
    except Exception as e:
        logger.error(f"Ошибка получения структуры файла {file_id}: {e}")
        return None


# ============================================================================
# CUSTOM CACHE MANAGER
# ============================================================================

class CacheManager:
    """
    Менеджер кэша для ручного управления инвалидацией.
    """

    @staticmethod
    def clear_all():
        """Очистка всего кэша Streamlit."""
        st.cache_data.clear()
        st.cache_resource.clear()
        logger.info("Весь кэш очищен")

    @staticmethod
    def clear_data_cache():
        """Очистка только data кэша."""
        st.cache_data.clear()
        logger.info("Data кэш очищен")

    @staticmethod
    def invalidate_function(func: Callable):
        """Инвалидация кэша конкретной функции."""
        try:
            func.clear()
            logger.info(f"Кэш функции {func.__name__} очищен")
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")


# ============================================================================
# CACHE KEY GENERATOR
# ============================================================================

def generate_cache_key(*args, **kwargs) -> str:
    """
    Генерация уникального ключа кэша из аргументов.
    """
    key_data = {
        "args": [str(arg) for arg in args],
        "kwargs": kwargs,
        "timestamp": datetime.now().isoformat()[:16]  # Минутная точность
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()[:12]


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

def cache_monitor(func: Callable) -> Callable:
    """
    Декоратор для мониторинга производительности кэшированных функций.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = datetime.now()
        result = func(*args, **kwargs)
        duration = (datetime.now() - start).total_seconds() * 1000  # ms

        if duration > 100:  # Предупреждение если > 100ms
            logger.warning(f"Медленная функция {func.__name__}: {duration:.2f}ms")
        else:
            logger.debug(f"Функция {func.__name__}: {duration:.2f}ms")

        return result

    return wrapper