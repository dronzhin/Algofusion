# state/session_manager.py
import streamlit as st
import logging
from typing import Any, Optional, Dict, List

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")

class SessionManager:
    """
    Централизованный менеджер для работы с session_state
    Обеспечивает типизацию и валидацию данных
    """

    # Ключи для session_state
    SHARED_FILE = "shared_file"
    BINARY_RESULTS = "binary_results"
    ROTATION_RESULTS = "rotation_results"
    LAST_UPLOADED_FILE = "last_uploaded_file"
    SHOW_LINE_STATE = "show_line_state"
    SESSION_INITIALIZED = "_session_initialized"

    @classmethod
    def get_shared_file(cls) -> Optional[Dict[str, Any]]:
        """Получить текущий файл из сессии"""
        file = st.session_state.get(cls.SHARED_FILE)
        logger.debug(f"Получен файл из сессии: {'да' if file else 'нет'}")
        return file

    @classmethod
    def set_shared_file(cls, file_info: Dict[str, Any]):
        """Сохранить файл в сессию"""
        try:
            st.session_state[cls.SHARED_FILE] = file_info
            st.session_state[cls.LAST_UPLOADED_FILE] = file_info["name"]
            logger.info(f"Файл сохранён в сессию: {file_info.get('name', 'без имени')}")
        except KeyError as e:
            logger.error(f"Ошибка при сохранении файла: отсутствует ключ {e}")
            raise ValueError(f"Некорректная структура file_info: {e}")

    @classmethod
    def clear_shared_file(cls):
        """Очистить файл из сессии"""
        removed = []
        if cls.SHARED_FILE in st.session_state:
            del st.session_state[cls.SHARED_FILE]
            removed.append(cls.SHARED_FILE)
        if cls.LAST_UPLOADED_FILE in st.session_state:
            del st.session_state[cls.LAST_UPLOADED_FILE]
            removed.append(cls.LAST_UPLOADED_FILE)
        if removed:
            logger.info(f"Удалены ключи из сессии: {removed}")
        else:
            logger.debug("Попытка очистки файла: файл не был загружен")

    @classmethod
    def get_binary_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты бинарной конвертации"""
        results = st.session_state.get(cls.BINARY_RESULTS)
        logger.debug(f"Получены бинарные результаты: {'да' if results else 'нет'}")
        return results

    @classmethod
    def set_binary_results(cls, images: List[bytes], threshold: int, filename: str):
        """Сохранить результаты бинарной конвертации"""
        st.session_state[cls.BINARY_RESULTS] = {
            "images": images,
            "threshold": threshold,
            "filename": filename
        }
        logger.info(f"Бинарные результаты сохранены: файл={filename}, порог={threshold}, изображений={len(images)}")

    @classmethod
    def clear_binary_results(cls):
        """Очистить результаты бинарной конвертации"""
        if cls.BINARY_RESULTS in st.session_state:
            del st.session_state[cls.BINARY_RESULTS]
            logger.info("Бинарные результаты удалены из сессии")
        else:
            logger.debug("Попытка очистки бинарных результатов: данные отсутствуют")

    @classmethod
    def get_rotation_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты выравнивания изображения"""
        results = st.session_state.get(cls.ROTATION_RESULTS)
        logger.debug(f"Получены результаты выравнивания: {'да' if results else 'нет'}")
        return results

    @classmethod
    def set_rotation_results(cls, results: Dict[str, Any]):
        """Сохранить результаты выравнивания изображения"""
        st.session_state[cls.ROTATION_RESULTS] = results
        angle = results.get("angle", "неизвестно")
        logger.info(f"Результаты выравнивания сохранены: угол={angle}°")

    @classmethod
    def clear_rotation_results(cls):
        """Очистить результаты выравнивания изображения"""
        if cls.ROTATION_RESULTS in st.session_state:
            del st.session_state[cls.ROTATION_RESULTS]
            logger.info("Результаты выравнивания удалены из сессии")
        else:
            logger.debug("Попытка очистки результатов выравнивания: данные отсутствуют")

    @classmethod
    def get_show_line_state(cls) -> bool:
        """Получить состояние чекбокса показа линии"""
        state = st.session_state.get(cls.SHOW_LINE_STATE, False)
        logger.debug(f"Состояние 'показать линию': {state}")
        return state

    @classmethod
    def set_show_line_state(cls, value: bool):
        """Установить состояние чекбокса показа линии"""
        st.session_state[cls.SHOW_LINE_STATE] = value
        logger.info(f"Состояние 'показать линию' установлено: {value}")

    # === ИНИЦИАЛИЗАЦИЯ ===
    @classmethod
    def initialize_session(cls):
        """Инициализация session_state — только один раз за сессию"""
        if st.session_state.get(cls.SESSION_INITIALIZED):
            return  # Уже инициализировано — выходим

        defaults = {
            cls.SHARED_FILE: None,
            cls.BINARY_RESULTS: None,
            cls.ROTATION_RESULTS: None,
            cls.LAST_UPLOADED_FILE: None,
            cls.SHOW_LINE_STATE: False
        }

        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
                logger.debug(f"Установлено значение по умолчанию для '{key}': {default_value}")

        # Устанавливаем флаг
        st.session_state[cls.SESSION_INITIALIZED] = True

    @classmethod
    def clear_all_results(cls):
        """Очистить все результаты обработки"""
        logger.info("Очистка всех результатов обработки")
        cls.clear_binary_results()
        cls.clear_rotation_results()
        cls.set_show_line_state(False)