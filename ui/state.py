# ui/state.py
"""
Управление session_state для Streamlit UI.
Инкапсулирует всю логику работы с состоянием сессии.
"""

import streamlit as st
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from shared.utils.logger import setup_logger
from core.state import get_app_state

logger = setup_logger("ui.state")


class SessionState:
    """
    Обёртка над st.session_state для типобезопасного доступа.
    """

    # Ключи состояния
    KEYS = {
        "current_page": "main",
        "editing_file_index": None,
        "export_logs": [],
        "file_cache": {},
        "last_refresh": None,
        "filters": {},
        "user_preferences": {},
        "pubsub": None,
        "redis_client": None,
        "file_service": None,
        "settings": None,
    }

    @classmethod
    def initialize(cls) -> "SessionState":
        """Инициализация состояния сессии."""
        for key, default_value in cls.KEYS.items():
            if key not in st.session_state:
                if isinstance(default_value, (list, dict)):
                    st.session_state[key] = default_value.copy()
                else:
                    st.session_state[key] = default_value

        logger.debug("SessionState инициализирован")
        return cls()

    @property
    def current_page(self) -> str:
        return st.session_state.current_page

    @current_page.setter
    def current_page(self, value: str):
        st.session_state.current_page = value
        logger.debug(f"Навигация: {value}")

    @property
    def editing_file_index(self) -> Optional[int]:
        return st.session_state.editing_file_index

    @editing_file_index.setter
    def editing_file_index(self, value: Optional[int]):
        st.session_state.editing_file_index = value

    @property
    def export_logs(self) -> List[Dict[str, str]]:
        return st.session_state.export_logs

    @property
    def file_cache(self) -> Dict[str, Any]:
        return st.session_state.file_cache

    @property
    def last_refresh(self) -> Optional[datetime]:
        return st.session_state.last_refresh

    @property
    def redis_client(self):
        return st.session_state.redis_client

    @property
    def file_service(self):
        return st.session_state.file_service

    def navigate(self, page: str, **kwargs):
        """Безопасная навигация между страницами."""
        st.session_state.current_page = page
        for key, value in kwargs.items():
            if key in self.KEYS:
                st.session_state[key] = value
        logger.info(f"Навигация: {page}")

    def add_log(self, status: str, message: str):
        """Добавление лога в сессию."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.export_logs.append({
            "time": timestamp,
            "status": status,
            "msg": message
        })
        # Храним последние 50 логов
        if len(st.session_state.export_logs) > 50:
            st.session_state.export_logs = st.session_state.export_logs[-50:]
        logger.debug(f"Лог добавлен: [{status}] {message}")

    def invalidate_cache(self, key: Optional[str] = None):
        """Инвалидация кэша."""
        if key:
            st.session_state.file_cache.pop(key, None)
            logger.debug(f"Кэш инвалидирован: {key}")
        else:
            st.session_state.file_cache = {}
            logger.debug("Весь кэш инвалидирован")

    def set_filter(self, filter_name: str, value: Any):
        """Установка фильтра."""
        if "filters" not in st.session_state:
            st.session_state.filters = {}
        st.session_state.filters[filter_name] = value
        self.invalidate_cache("files_list")

    def get_filter(self, filter_name: str, default: Any = None) -> Any:
        """Получение фильтра."""
        return st.session_state.get("filters", {}).get(filter_name, default)

    def reset_filters(self):
        """Сброс всех фильтров."""
        st.session_state.filters = {}
        self.invalidate_cache("files_list")
        logger.info("Фильтры сброшены")

    def update_refresh_time(self):
        """Обновление времени последнего обновления."""
        st.session_state.last_refresh = datetime.now()

    def get_uptime(self) -> str:
        """Получение времени работы сессии."""
        app_state = get_app_state()
        app_state.update_uptime()
        hours = app_state.uptime_seconds // 3600
        minutes = (app_state.uptime_seconds % 3600) // 60
        return f"{hours}ч {minutes}м"

    def to_dict(self) -> Dict[str, Any]:
        """Экспорт состояния для отладки."""
        return {
            "current_page": self.current_page,
            "editing_file_index": self.editing_file_index,
            "logs_count": len(self.export_logs),
            "cache_keys": list(self.file_cache.keys()),
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "filters": st.session_state.get("filters", {}),
            "uptime": self.get_uptime()
        }


# Глобальный экземпляр для удобства
def get_session_state() -> SessionState:
    """Получение экземпляра SessionState."""
    return SessionState.initialize()