# ui/cache.py
"""
Слой кэширования для Streamlit UI.
"""

import streamlit as st
from typing import Any, Dict, List, Optional
from shared.utils.logger import setup_logger

logger = setup_logger("ui.cache")

# ============================================================================
# 📦 КОНФИГУРАЦИЯ TTL
# ============================================================================

CACHE_TTL = {
    "file_stats": 60,          # 1 минута (статистика)
    "files_list": 30,          # 30 секунд (файлы — автообновление)
    "redis_connection": 86400, # 24 часа (подключение)
}


# ============================================================================
# 🔗 CACHE DECORATORS
# ============================================================================

@st.cache_resource(ttl=CACHE_TTL["redis_connection"])
def get_redis_client_cached():
    """Кэшированное подключение к Redis."""
    from core.services.redis_client import get_redis_client
    logger.info("🔌 Создание нового Redis подключения (кэшировано)")
    return get_redis_client()


@st.cache_data(ttl=CACHE_TTL["file_stats"])
def get_file_stats_cached(
    _redis_client: Any,
    _cache_key: str = "default"
) -> Dict[str, Any]:
    """Статистика файлов (кэш 1 минута)."""
    try:
        if isinstance(_redis_client, list):
            files = _redis_client
        elif hasattr(_redis_client, 'get_all_files'):
            files = _redis_client.get_all_files()
        else:
            return {"total": 0, "completed": 0, "processing": 0, "failed": 0, "exported": 0, "success_rate": "0%"}

        total = len(files)
        if total == 0:
            return {"total": 0, "completed": 0, "processing": 0, "failed": 0, "exported": 0, "success_rate": "0%"}

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
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return {"total": 0, "completed": 0, "processing": 0, "failed": 0, "exported": 0, "success_rate": "0%"}


@st.cache_data(ttl=CACHE_TTL["files_list"])
def get_files_from_redis_cached(
    _redis_client: Any,
    _cache_key: str = "default"
) -> List[Dict[str, Any]]:
    """Список файлов (кэш 30 секунд, автообновление)."""
    try:
        if isinstance(_redis_client, list):
            return _redis_client
        if hasattr(_redis_client, 'get_all_files'):
            files = _redis_client.get_all_files()
            logger.debug(f"📦 Загружено {len(files)} файлов из Redis (ключ: {_cache_key})")
            return files
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка получения файлов: {e}")
        return []


# ============================================================================
# 🧹 CACHE MANAGER
# ============================================================================

class CacheManager:
    """Менеджер кэша для ручного управления инвалидацией."""

    @staticmethod
    def clear_all():
        """Очистка всего кэша Streamlit."""
        st.cache_data.clear()
        st.cache_resource.clear()
        logger.info("🗑️ Весь кэш очищен")

    @staticmethod
    def clear_data_cache():
        """Очистка только data кэша."""
        st.cache_data.clear()
        logger.info("🗑️ Data кэш очищен")

    @staticmethod
    def invalidate_function(func):
        """Инвалидация кэша конкретной функции."""
        try:
            func.clear()
            logger.info(f"🗑️ Кэш функции {func.__name__} очищен")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")