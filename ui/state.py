# ui/state.py
"""
Управление состоянием сессии Streamlit.
Использует singleton-паттерн для глобального доступа.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import streamlit as st

from shared.utils.logger import setup_logger

logger = setup_logger("ui.state")


@dataclass
class SessionState:
    """Глобальное состояние сессии приложения."""

    # Навигация
    current_page: str = "main"
    editing_file_index: Optional[int] = None

    # Сервисы (инициализируются отдельно)
    redis_client: Any = None
    file_service: Any = None
    settings: Any = None

    # Кэширование
    cache_timestamp: float = field(default_factory=time.time)
    last_refresh: Optional[datetime] = None

    # Фильтры
    _filters: Dict[str, List[str]] = field(default_factory=dict)

    # Логи
    _logs: List[Dict[str, str]] = field(default_factory=list)
    max_logs: int = 100

    # Pub/Sub
    pubsub: Any = None

    # ← Поля для совместимости с UI (значения синхронизируются через st.session_state)
    auto_refresh: bool = True
    refresh_interval: int = 10
    _cache_buster: str = field(default_factory=lambda: f"v{time.time()}", repr=False)

    def get_filter(self, key: str, default: List[str] = None) -> List[str]:
        """Получение фильтра по ключу."""
        return self._filters.get(key, default or [])

    def set_filter(self, key: str, value: List[str]):
        """Установка фильтра по ключу."""
        self._filters[key] = value

    def add_log(self, status: str, message: str):
        """Добавление записи в лог."""
        from datetime import datetime
        self._logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": status,
            "msg": message
        })
        # Ограничиваем размер лога
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]

    def get_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        """Получение последних логов."""
        return self._logs[-limit:] if self._logs else []

    def clear_logs(self):
        """Очистка логов."""
        self._logs.clear()

    def invalidate_cache(self):
        """Инвалидация кэша — обновляет таймстамп и cache_buster."""
        self.cache_timestamp = time.time()
        self._cache_buster = f"v{time.time()}"
        logger.debug(f"Кэш инвалидирован: {self._cache_buster}")

    def update_refresh_time(self):
        """Обновляет время последнего запроса."""
        self.last_refresh = datetime.now()

    def navigate(self, page: str, **kwargs):
        """Навигация к странице с параметрами."""
        self.current_page = page
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_uptime(self) -> str:
        """Время работы приложения."""
        if not self.last_refresh:
            return "—"
        delta = datetime.now() - self.last_refresh
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_SESSION_STATE_KEY = "_algofusion_session_state"


def get_session_state() -> SessionState:
    """
    Получение глобального экземпляра SessionState.
    Использует streamlit.session_state для сохранения между rerun.
    """
    if _SESSION_STATE_KEY not in st.session_state:
        logger.info("Инициализация нового SessionState")
        st.session_state[_SESSION_STATE_KEY] = SessionState()

    return st.session_state[_SESSION_STATE_KEY]


def reset_session_state():
    """Сброс состояния (для тестов или принудительного обновления)."""
    if _SESSION_STATE_KEY in st.session_state:
        del st.session_state[_SESSION_STATE_KEY]
    logger.info("SessionState сброшен")