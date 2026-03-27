# ui/state.py
"""
Управление состоянием сессии Streamlit.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from shared.utils.logger import setup_logger

logger = setup_logger("ui.state")


@dataclass
class SessionState:
    """Глобальное состояние сессии приложения."""

    # 🧭 Навигация
    current_page: str = "main"

    # 🔧 Сервисы
    redis_client: Any = None
    file_service: Any = None
    settings: Any = None

    # 🔑 Кэш
    cache_buster: str = field(default_factory=lambda: f"v{int(time.time())}", repr=False)
    last_refresh: Optional[datetime] = None

    # 📊 Данные
    _filters: Dict[str, List[str]] = field(default_factory=dict)
    _logs: List[Dict[str, str]] = field(default_factory=list)
    max_logs: int = 100

    # 📡 Pub/Sub
    pubsub: Any = None

    # 🔔 Флаги
    pending_events: bool = False

    # ========================================================================
    # МЕТОДЫ: ЛОГИ
    # ========================================================================

    def add_log(self, status: str, message: str):
        """Добавление записи в лог."""
        self._logs.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "status": status,
            "msg": message
        })
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]
        self.pending_events = True

    def get_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        """Получение последних логов."""
        return self._logs[-limit:] if self._logs else []

    def clear_logs(self):
        """Очистка логов."""
        self._logs.clear()

    # ========================================================================
    # МЕТОДЫ: КЭШИРОВАНИЕ
    # ========================================================================

    def invalidate_cache(self):
        """Инвалидация кэша."""
        self.cache_buster = f"v{int(time.time())}"
        logger.debug(f"🗑️ Кэш инвалидирован: {self.cache_buster}")

    def update_refresh_time(self):
        """Обновляет время последнего запроса."""
        self.last_refresh = datetime.now(timezone.utc)

    # ========================================================================
    # МЕТОДЫ: ФИЛЬТРЫ И НАВИГАЦИЯ
    # ========================================================================

    def get_filter(self, key: str, default: List[str] = None) -> List[str]:
        return self._filters.get(key, default or [])

    def set_filter(self, key: str, value: List[str]):
        self._filters[key] = value

    def navigate(self, page: str, **kwargs):
        self.current_page = page
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_uptime(self) -> str:
        if not self.last_refresh:
            return "—"
        delta = datetime.now(timezone.utc) - self.last_refresh
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_SESSION_STATE_KEY = "_algofusion_session_state"


def get_session_state() -> SessionState:
    if _SESSION_STATE_KEY not in st.session_state:
        logger.info("🔄 Инициализация нового SessionState")
        st.session_state[_SESSION_STATE_KEY] = SessionState()
    return st.session_state[_SESSION_STATE_KEY]


def reset_session_state():
    if _SESSION_STATE_KEY in st.session_state:
        del st.session_state[_SESSION_STATE_KEY]
    logger.info("🗑️ SessionState сброшен")