import streamlit as st
from typing import Any, Optional, Dict, List

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
    SHOW_LINE_STATE = "show_line_state"  # Новое состояние для чекбокса

    @classmethod
    def get_shared_file(cls) -> Optional[Dict[str, Any]]:
        """Получить текущий файл из сессии"""
        return st.session_state.get(cls.SHARED_FILE)

    @classmethod
    def set_shared_file(cls, file_info: Dict[str, Any]):
        """Сохранить файл в сессию"""
        st.session_state[cls.SHARED_FILE] = file_info
        st.session_state[cls.LAST_UPLOADED_FILE] = file_info["name"]

    @classmethod
    def clear_shared_file(cls):
        """Очистить файл из сессии"""
        if cls.SHARED_FILE in st.session_state:
            del st.session_state[cls.SHARED_FILE]
        if cls.LAST_UPLOADED_FILE in st.session_state:
            del st.session_state[cls.LAST_UPLOADED_FILE]

    @classmethod
    def get_binary_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты бинарной конвертации"""
        return st.session_state.get(cls.BINARY_RESULTS)

    @classmethod
    def set_binary_results(cls, images: List[bytes], threshold: int, filename: str):
        """Сохранить результаты бинарной конвертации"""
        st.session_state[cls.BINARY_RESULTS] = {
            "images": images,
            "threshold": threshold,
            "filename": filename
        }

    @classmethod
    def clear_binary_results(cls):
        """Очистить результаты бинарной конвертации"""
        if cls.BINARY_RESULTS in st.session_state:
            del st.session_state[cls.BINARY_RESULTS]

    # === НОВЫЕ МЕТОДЫ ДЛЯ ВЫРАВНИВАНИЯ ===
    @classmethod
    def get_rotation_results(cls) -> Optional[Dict[str, Any]]:
        """Получить результаты выравнивания изображения"""
        return st.session_state.get(cls.ROTATION_RESULTS)

    @classmethod
    def set_rotation_results(cls, results: Dict[str, Any]):
        """Сохранить результаты выравнивания изображения"""
        st.session_state[cls.ROTATION_RESULTS] = results

    @classmethod
    def clear_rotation_results(cls):
        """Очистить результаты выравнивания изображения"""
        if cls.ROTATION_RESULTS in st.session_state:
            del st.session_state[cls.ROTATION_RESULTS]

    @classmethod
    def get_show_line_state(cls) -> bool:
        """Получить состояние чекбокса показа линии"""
        return st.session_state.get(cls.SHOW_LINE_STATE, False)

    @classmethod
    def set_show_line_state(cls, value: bool):
        """Установить состояние чекбокса показа линии"""
        st.session_state[cls.SHOW_LINE_STATE] = value

    # === ИНИЦИАЛИЗАЦИЯ ===
    @classmethod
    def initialize_session(cls):
        """Инициализация session_state при запуске приложения"""
        if cls.SHARED_FILE not in st.session_state:
            st.session_state[cls.SHARED_FILE] = None
        if cls.BINARY_RESULTS not in st.session_state:
            st.session_state[cls.BINARY_RESULTS] = None
        if cls.ROTATION_RESULTS not in st.session_state:
            st.session_state[cls.ROTATION_RESULTS] = None
        if cls.LAST_UPLOADED_FILE not in st.session_state:
            st.session_state[cls.LAST_UPLOADED_FILE] = None
        if cls.SHOW_LINE_STATE not in st.session_state:
            st.session_state[cls.SHOW_LINE_STATE] = False

    @classmethod
    def clear_all_results(cls):
        """Очистить все результаты обработки"""
        cls.clear_binary_results()
        cls.clear_rotation_results()
        cls.set_show_line_state(False)