# ui/cache.py
"""
Слой кэширования для Streamlit UI.
🔹 Включает строгую валидацию целостности файлов и однократную очистку при старте.
"""

import streamlit as st
from typing import Any, Dict, List, Optional
from pathlib import Path
from shared.utils.logger import setup_logger

logger = setup_logger("ui.cache")

# ============================================================================
# 📦 КОНФИГУРАЦИЯ TTL И ПУТЕЙ
# ============================================================================

CACHE_TTL = {
    "file_stats": 15000,
    "files_list": 15000,
    "file_details": 15000,
    "redis_connection": 86400,
}

BASE_FILES_DIR = Path("/shared/files")

# Директории, которые должны существовать для разных статусов
REQUIRED_DIRS_BY_STATUS = {
    "uploaded": ["original"],
    "processing": ["original"],
    "completed": ["original", "preprocessed", "ocr", "llm"],
    "exported": ["original", "preprocessed", "ocr", "llm", "export"],
    "failed": ["original"]  # Даже при ошибке должен быть оригинал
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


@st.cache_data(ttl=CACHE_TTL["file_stats"], show_spinner="Загрузка статистики...")
def get_file_stats_cached(_redis_client, _cache_key: str) -> Dict[str, Any]:
    """Получение статистики обработки файлов."""
    if not _redis_client:
        return _empty_stats()

    try:
        files = _redis_client.get_all_files()
        stats = {
            "uploaded": 0, "preprocessing": 0, "ocr": 0, "llm": 0,
            "pending_export": 0, "exported": 0, "failed": 0,
            "total": 0,
        }

        for file_data in files:
            status = file_data.get("status", "unknown")
            current_module = file_data.get("current_module", "")
            export_status = file_data.get("export_status", "pending")
            file_id = file_data.get("file_id", "")

            # Пропускаем файлы, у которых нет директории на диске
            if not (BASE_FILES_DIR / file_id).exists():
                continue

            stats["total"] += 1
            if status == "failed":
                stats["failed"] += 1
            elif status == "uploaded":
                stats["uploaded"] += 1
            elif status == "processing":
                if current_module == "preprocess":
                    stats["preprocessing"] += 1
                elif current_module == "ocr":
                    stats["ocr"] += 1
                elif current_module == "llm":
                    stats["llm"] += 1
                else:
                    stats["uploaded"] += 1
            elif status in ("completed", "exported"):
                if export_status == "success":
                    stats["exported"] += 1
                else:
                    stats["pending_export"] += 1

        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return _empty_stats()


def _empty_stats() -> Dict[str, Any]:
    return {"uploaded": 0, "preprocessing": 0, "ocr": 0, "llm": 0, "pending_export": 0, "exported": 0, "failed": 0,
            "total": 0}


def _is_file_integrity_valid(file_data: Dict[str, Any]

) -> bool:
    """
    Проверяет целостность файла на диске.
    Возвращает True только если:
    1. Базовая директория существует
    2. Обязательные для текущего статуса папки присутствуют
    """
    file_id = file_data.get("file_id")
    status = file_data.get("status", "unknown")
    base_path = BASE_FILES_DIR / file_id

    if not base_path.exists():
        return False

    required = REQUIRED_DIRS_BY_STATUS.get(status, ["original"])
    missing = [d for d in required if not (base_path / d).exists()]

    if missing:
        logger.debug(f"⚠️ Нарушена целостность {file_id} ({status}): отсутствуют {missing}")
        return False

    return True


@st.cache_data(ttl=CACHE_TTL["files_list"], show_spinner=False)
def get_files_from_redis_cached(
        _redis_client: Any,
        _cache_key: str = "default",
        _validation_seed: str = "v2"
) -> List[Dict[str, Any]]:
    """
    Получает список файлов из Redis с ЖЁСТКОЙ валидацией целостности.
    Фильтрует все записи, у которых удалены этапы обработки или базовая папка.
    """
    if not _redis_client or not hasattr(_redis_client, 'get_all_files'):
        return []

    try:
        all_files = _redis_client.get_all_files()
        valid_files = []

        for file_data in all_files:
            if _is_file_integrity_valid(file_data):
                valid_files.append(file_data)
            else:
                # Логируем, но не шумим в UI
                logger.debug(f"🗑️ Исключён повреждённый файл: {file_data.get('file_id')}")

        return valid_files

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в get_files_from_redis_cached: {e}", exc_info=True)
        return []


@st.cache_data(ttl=CACHE_TTL["file_details"], show_spinner=False)
def get_file_details_cached(_redis_client: Any, file_id: str, _validation_seed: str = "v1") -> Optional[Dict[str, Any]]:
    """Детали файла с проверкой целостности."""
    if not _redis_client or not file_id:
        return None
    try:
        file_data = _redis_client.get_file_status(file_id)
        if not file_data:
            return None
        return file_data if _is_file_integrity_valid(file_data) else None
    except Exception as e:
        logger.error(f"Ошибка получения деталей {file_id}: {e}")
        return None


# ============================================================================
# 🚀 STARTUP VALIDATION & CLEANUP
# ============================================================================

@st.cache_resource
def run_startup_validation(_redis_client, _file_service) -> Dict[str, int]:
    """
    🔹 Запускается ОДИН РАЗ при старте UI-сервера.
    Удаляет из Redis записи, у которых удалена базовая директория.
    🔹 Также очищает индекс fingerprint для удалённых файлов.
    """
    logger.info("🧹 Запуск валидации файлов при старте UI...")
    if not _redis_client or not _file_service:
        return {"cleaned": 0, "checked": 0}

    try:
        all_files = _redis_client.get_all_files()
        cleaned = 0

        for file_data in all_files:
            file_id = file_data.get("file_id", "")
            base_path = BASE_FILES_DIR / file_id

            # Если базовой директории нет → запись в Redis мёртвая
            if not base_path.exists():
                try:
                    _redis_client.delete_file_status(file_id)
                    # 🔹 Удаляем индекс fingerprint, если есть
                    fp = file_data.get("metadata", {}).get("file_fingerprint")
                    if fp:
                        from shared.utils.helpers import FILE_FINGERPRINT_INDEX
                        _redis_client.delete(f"{FILE_FINGERPRINT_INDEX}:{fp}")
                        logger.debug(f"🗑️ Удалён индекс fingerprint: {fp}")
                    cleaned += 1
                    logger.info(f"🗑️ Удалена мёртвая запись из Redis: {file_id}")
                except Exception as e:
                    logger.error(f"Ошибка удаления {file_id}: {e}")

        # Принудительно очищаем кэш после валидации
        st.cache_data.clear()
        logger.info(f"✅ Валидация завершена: проверено {len(all_files)}, удалено {cleaned}")
        return {"cleaned": cleaned, "checked": len(all_files)}

    except Exception as e:
        logger.error(f"❌ Ошибка валидации при старте: {e}", exc_info=True)
        return {"cleaned": 0, "checked": 0}

# ============================================================================
# 🧹 CACHE MANAGER
# ============================================================================

class CacheManager:
    @staticmethod
    def clear_all():
        st.cache_data.clear()
        st.cache_resource.clear()
        logger.info("🗑️ Весь кэш очищен")

    @staticmethod
    def clear_data_cache():
        st.cache_data.clear()
        logger.info("🗑️ Data-кэш очищен")

    @staticmethod
    def invalidate_files_list():
        try:
            get_files_from_redis_cached.clear()
            logger.info("🗑️ Кэш списка файлов инвалидирован")
        except Exception as e:
            logger.error(f"Ошибка инвалидации: {e}")