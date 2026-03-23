# core/state.py
"""
Глобальное состояние приложения (не зависит от Streamlit).
Используется для хранения конфигурации и общих данных.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone  # ← Добавили timezone
from shared.utils.logger import setup_logger

logger = setup_logger("core.state")


@dataclass
class AppState:
    """
    Глобальное состояние приложения.
    Не зависит от Streamlit session_state.
    """

    # Конфигурация
    app_name: str = "Algofusion File Processor"
    app_version: str = "0.1.0"
    debug_mode: bool = False

    # Статистика (кэшированная)
    total_files_processed: int = 0
    total_errors: int = 0
    last_stats_update: Optional[datetime] = None

    # Активные подключения
    redis_connected: bool = False
    redis_last_ping: Optional[datetime] = None

    # Системная информация
    # ← Используем timezone-aware datetime
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: int = 0

    def update_uptime(self):
        """Обновляет время работы приложения."""
        # ← Используем timezone-aware datetime
        now = datetime.now(timezone.utc)
        self.uptime_seconds = int((now - self.started_at).total_seconds())

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "debug_mode": self.debug_mode,
            "total_files_processed": self.total_files_processed,
            "total_errors": self.total_errors,
            "last_stats_update": self.last_stats_update.isoformat() if self.last_stats_update else None,
            "redis_connected": self.redis_connected,
            "redis_last_ping": self.redis_last_ping.isoformat() if self.redis_last_ping else None,
            "started_at": self.started_at.isoformat(),  # timezone-aware корректно сериализуется
            "uptime_seconds": self.uptime_seconds
        }


# Глобальный синглтон
_app_state: Optional[AppState] = None


def get_app_state() -> AppState:
    """Получение глобального состояния (синглтон)."""
    global _app_state
    if _app_state is None:
        _app_state = AppState()
        logger.info("AppState инициализирован")
    return _app_state


def reset_app_state():
    """Сброс состояния (для тестов)."""
    global _app_state
    _app_state = None
    logger.info("AppState сброшен")
