# ui/state.py
"""
Управление состоянием сессии Streamlit.
"""

import time
import json
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
    _pubsub: Any = None
    _subscribed_channels: List[str] = field(default_factory=lambda: ["files:events", "1c:export"])
    _last_event_check: float = 0.0
    _event_check_interval: float = 1.0  # Проверять события не чаще 1 раза в секунду

    # 🔔 Флаги
    pending_events: bool = False

    # ========================================================================
    # МЕТОДЫ: ЛОГИ
    # ========================================================================

    def add_log(self, status: str, message: str, time_str: Optional[str] = None) -> None:
        """
        Добавляет запись в журнал событий.

        Args:
            status: Статус ("OK", "ERROR", "INFO", "WARNING")
            message: Текст сообщения
            time_str: Время в формате "HH:MM:SS" (по умолчанию: сейчас)
        """
        if time_str is None:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        self._logs.append({
            "time": time_str,
            "status": status,
            "msg": message
        })

        # Ограничиваем размер журнала
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]

        self.pending_events = True

    def get_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        """Получение последних логов для отображения."""
        return self._logs[-limit:] if self._logs else []

    def clear_logs(self) -> None:
        """Очистка журнала событий."""
        self._logs.clear()
        self.pending_events = False

    # ========================================================================
    # МЕТОДЫ: ОБРАБОТКА СОБЫТИЙ ОТ ПРОЦЕССОРА
    # ========================================================================

    def subscribe_to_events(self) -> None:
        """
        Подписывается на каналы событий Redis.
        Вызывать один раз при инициализации.
        """
        if not self.redis_client or self._pubsub is not None:
            return

        try:
            self._pubsub = self.redis_client.subscribe(self._subscribed_channels)
            logger.info(f"✅ Подписка на события: {self._subscribed_channels}")
        except Exception as e:
            logger.error(f"❌ Ошибка подписки на события: {e}")

    def process_events(self) -> None:
        """
        Обрабатывает новые события из Redis и добавляет их в журнал.
        Вызывать на каждом рендере страницы (в render_main_page).
        """
        # Проверяем не чаще чем _event_check_interval секунд
        now = time.time()
        if now - self._last_event_check < self._event_check_interval:
            return

        self._last_event_check = now

        if not self.redis_client or self._pubsub is None:
            return

        try:
            # Неблокирующее получение сообщений
            message = self._pubsub.get_message(timeout=0)

            while message:
                if message.get("type") in ("message", "pmessage"):
                    try:
                        event = json.loads(message["data"])
                        self._handle_event(event)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"⚠️ Не удалось распарсить событие: {e}")

                message = self._pubsub.get_message(timeout=0)

        except Exception as e:
            logger.debug(f"⚠️ Ошибка обработки событий: {e}")

    def _handle_event(self, event: Dict[str, Any]) -> None:
        """
        Преобразует событие Redis в запись журнала.

        Поддерживаемые типы:
        - file_uploaded
        - file_status_changed
        - processing_error
        """
        event_type = event.get("type")
        file_id = event.get("file_id", "unknown")
        file_id_short = file_id[:8] if len(file_id) >= 8 else file_id
        timestamp = event.get("timestamp", "")

        # Форматируем время из ISO в "HH:MM:SS"
        time_str = "—:—:—"
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                pass

        # Обработка по типу события
        if event_type == "file_uploaded":
            filename = event.get("filename", "unknown")
            file_type = event.get("file_type", "unknown")
            self.add_log("OK", f"📁 Новый файл: {filename} ({file_id_short}...) [{file_type}]")

        elif event_type == "file_status_changed":
            status = event.get("status", "unknown")
            module = event.get("current_module", "")
            error = event.get("error")
            completed = event.get("completed_modules", [])

            if status == "processing" and module == "preprocess":
                self.add_log("INFO", f"🔄 Предобработка: {file_id_short}...")

            elif status == "completed" and module is None:
                modules_str = ", ".join(completed) if completed else "все"
                self.add_log("OK", f"✅ Обработка завершена: {file_id_short}... [{modules_str}]")

            elif status == "failed":
                msg = f"❌ Ошибка: {error}" if error else "❌ Ошибка обработки"
                self.add_log("ERROR", f"{msg} ({file_id_short}...)")

        elif event_type == "processing_error":
            error = event.get("error", "Неизвестная ошибка")
            module = event.get("module", "unknown")
            self.add_log("ERROR", f"⚠️ {module}: {error}")

    # ========================================================================
    # МЕТОДЫ: КЭШИРОВАНИЕ
    # ========================================================================

    def invalidate_cache(self) -> None:
        """Инвалидация кэша."""
        self.cache_buster = f"v{int(time.time())}"
        logger.debug(f"🗑️ Кэш инвалидирован: {self.cache_buster}")

    def update_refresh_time(self) -> None:
        """Обновляет время последнего запроса."""
        self.last_refresh = datetime.now(timezone.utc)

    # ========================================================================
    # МЕТОДЫ: ФИЛЬТРЫ И НАВИГАЦИЯ
    # ========================================================================

    def get_filter(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        return self._filters.get(key, default or [])

    def set_filter(self, key: str, value: List[str]) -> None:
        self._filters[key] = value

    def navigate(self, page: str, **kwargs) -> None:
        """Навигация между страницами."""
        self.current_page = page
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_uptime(self) -> str:
        """Расчёт времени с последнего обновления."""
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
    """Получение или создание сессии (синглтон)."""
    if _SESSION_STATE_KEY not in st.session_state:
        logger.info("🔄 Инициализация нового SessionState")
        st.session_state[_SESSION_STATE_KEY] = SessionState()
    return st.session_state[_SESSION_STATE_KEY]


def reset_session_state() -> None:
    """Сброс сессии (для отладки)."""
    if _SESSION_STATE_KEY in st.session_state:
        del st.session_state[_SESSION_STATE_KEY]
    logger.info("🗑️ SessionState сброшен")