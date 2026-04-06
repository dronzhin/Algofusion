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
    "file_stats": 30,          # 1 минута (статистика)
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


# ui/cache.py

@st.cache_data(ttl=30, show_spinner="Загрузка статистики...")
def get_file_stats_cached(_redis_client, _cache_key: str) -> Dict[str, Any]:
    """
    Получение статистики обработки файлов из Redis.

    Returns:
        Dict с метриками по категориям:
        - uploaded: Загружено (ожидают обработки)
        - preprocessing: В предобработке
        - ocr: В OCR
        - llm: В LLM
        - pending_export: Обработаны, ожидают экспорта в 1С
        - exported: Экспортировано в 1С
        - failed: Ошибки
    """
    if not _redis_client:
        return _empty_stats()

    try:
        # Получаем все файлы из Redis
        files = _redis_client.get_all_files()

        # 🔹 Инициализируем счётчики по категориям
        stats = {
            "uploaded": 0,
            "preprocessing": 0,
            "ocr": 0,
            "llm": 0,
            "pending_export": 0,
            "exported": 0,
            "failed": 0,
            "total": len(files),
        }

        # 🔹 Распределяем файлы по категориям
        for file_data in files:
            status = file_data.get("status", "unknown")
            current_module = file_data.get("current_module", "")
            completed_modules = set(file_data.get("completed_modules", []))
            export_status = file_data.get("export_status", "pending")

            # 🔹 Обработка по статусу
            if status == "failed":
                stats["failed"] += 1

            elif status == "uploaded":
                # Файл загружен, но ещё не начал обрабатываться
                stats["uploaded"] += 1

            elif status == "processing":
                # Файл в обработке — определяем по current_module
                if current_module == "preprocess":
                    stats["preprocessing"] += 1
                elif current_module == "ocr":
                    stats["ocr"] += 1
                elif current_module == "llm":
                    stats["llm"] += 1
                else:
                    # Неизвестный модуль — считаем как "в обработке"
                    stats["uploaded"] += 1

            elif status == "completed":
                # Файл завершён — проверяем статус экспорта
                if export_status == "success":
                    stats["exported"] += 1
                else:
                    # Завершён, но ещё не экспортирован
                    stats["pending_export"] += 1

            elif status == "exported":
                # Явный статус экспорта (если используется)
                stats["exported"] += 1

        return stats

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return _empty_stats()


def _empty_stats() -> Dict[str, Any]:
    """Пустая статика для случая ошибки."""
    return {
        "uploaded": 0, "preprocessing": 0, "ocr": 0, "llm": 0,
        "pending_export": 0, "exported": 0, "failed": 0,
        "total": 0,
    }


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