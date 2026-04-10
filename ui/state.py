# ui/state.py
"""
Управление состоянием сессии Streamlit.
🔹 Добавлена обработка событий типа "log_only" — только журнал, никаких других эффектов.
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
    _event_check_interval: float = 1.0

    # 🔔 Флаги
    pending_events: bool = False

    def __post_init__(self):
        if not hasattr(self, '_pubsub') or self._pubsub is None:
            object.__setattr__(self, '_pubsub', None)
        if not hasattr(self, '_logs'):
            object.__setattr__(self, '_logs', [])
        if not hasattr(self, '_filters'):
            object.__setattr__(self, '_filters', {})

    # ========================================================================
    # МЕТОДЫ: ЛОГИ
    # ========================================================================

    def add_log(self, status: str, message: str, time_str: Optional[str] = None) -> None:
        if time_str is None:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if not hasattr(self, '_logs'):
            object.__setattr__(self, '_logs', [])
        self._logs.append({"time": time_str, "status": status, "msg": message})
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]
        self.pending_events = True

    def get_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        if not hasattr(self, '_logs'):
            return []
        return self._logs[-limit:] if self._logs else []

    def clear_logs(self) -> None:
        if hasattr(self, '_logs'):
            self._logs.clear()
        self.pending_events = False

    # ========================================================================
    # МЕТОДЫ: ОБРАБОТКА СОБЫТИЙ
    # ========================================================================

    def subscribe_to_events(self) -> None:
        if not self.redis_client:
            return
        current_pubsub = getattr(self, '_pubsub', None)
        if current_pubsub is not None:
            return
        try:
            pubsub = self.redis_client.subscribe(self._subscribed_channels)
            object.__setattr__(self, '_pubsub', pubsub)
            logger.info(f"✅ Подписка на события: {self._subscribed_channels}")
        except Exception as e:
            logger.error(f"❌ Ошибка подписки на события: {e}")

    def process_events(self) -> None:
        now = time.time()
        last_check = getattr(self, '_last_event_check', 0.0)
        interval = getattr(self, '_event_check_interval', 1.0)
        if now - last_check < interval:
            return
        object.__setattr__(self, '_last_event_check', now)

        if not self.redis_client:
            return
        pubsub = getattr(self, '_pubsub', None)
        if pubsub is None:
            return

        try:
            message = pubsub.get_message(timeout=0)
            while message:
                if message.get("type") in ("message", "pmessage"):
                    try:
                        event = json.loads(message["data"])
                        self._handle_event(event)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"⚠️ Не удалось распарсить событие: {e}")
                message = pubsub.get_message(timeout=0)
        except Exception as e:
            logger.debug(f"⚠️ Ошибка обработки событий: {e}")

    def _handle_event(self, event: Dict[str, Any]) -> None:
        """
        Обработчик событий из Redis.
        🔹 type="log_only" → только add_log(), возврат без других действий.
        """
        event_type = event.get("type")

        # 🔹 СПЕЦИАЛЬНЫЙ ТИП: только лог, никаких других эффектов
        if event_type == "log_only":
            level = event.get("log_level", "INFO")
            msg = event.get("log_msg", str(event))
            timestamp = event.get("timestamp", "")

            # Форматируем время для лога
            time_str = "—:—:—"
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except:
                    pass

            self.add_log(level, msg, time_str)
            return  # ← КЛЮЧЕВОЕ: выходим, не выполняем остальную логику

        # Стандартная обработка событий
        file_id = event.get("file_id", "unknown")
        file_id_short = file_id[:8] if len(file_id) >= 8 else file_id
        filename = event.get("filename")
        page_count = event.get("page_count")

        if filename:
            filename_display = f"{filename} ({page_count} стр.)" if page_count and page_count > 1 else filename
        else:
            filename_display = f"{file_id_short}..."

        timestamp = event.get("timestamp", "")
        time_str = "—:—:—"
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                pass

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
                self.add_log("INFO", f"🔧 Предобработка: {filename_display}")
            elif status == "processing" and module == "ocr":
                self.add_log("INFO", f"🔤 OCR: {filename_display}")
            elif status == "processing" and module == "llm":
                self.add_log("INFO", f"🧠 LLM: {filename_display}")
            elif status == "completed" and module is None:
                if "ocr" in completed and "preprocess" in completed:
                    self.add_log("OK", f"✅ OCR завершён: {filename_display}")
                elif "preprocess" in completed and "ocr" not in completed:
                    self.add_log("OK", f"✅ Предобработка завершена: {filename_display}")
                elif "llm" in completed:
                    self.add_log("OK", f"✅ LLM завершён: {filename_display}")
                else:
                    modules_str = ", ".join(completed) if completed else "все"
                    if page_count and page_count > 1:
                        self.add_log("OK", f"✅ Завершено: {filename_display} ({page_count} файлов) [{modules_str}]")
                    else:
                        self.add_log("OK", f"✅ Завершено: {filename_display} [{modules_str}]")
            elif status == "failed":
                msg = f"❌ Ошибка: {error}" if error else "❌ Ошибка обработки"
                self.add_log("ERROR", f"{msg} ({filename_display})")

        elif event_type == "processing_error":
            error = event.get("error", "Неизвестная ошибка")
            module = event.get("module", "unknown")
            self.add_log("ERROR", f"⚠️ {module}: {error} ({filename_display})")

    # ========================================================================
    # МЕТОДЫ: КЭШИРОВАНИЕ
    # ========================================================================

    def invalidate_cache(self) -> None:
        self.cache_buster = f"v{int(time.time())}"
        logger.debug(f"🗑️ Кэш инвалидирован: {self.cache_buster}")

    def update_refresh_time(self) -> None:
        self.last_refresh = datetime.now(timezone.utc)

    # ========================================================================
    # МЕТОДЫ: ФИЛЬТРЫ И НАВИГАЦИЯ
    # ========================================================================

    def get_filter(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        return self._filters.get(key, default or [])

    def set_filter(self, key: str, value: List[str]) -> None:
        self._filters[key] = value

    def navigate(self, page: str, **kwargs) -> None:
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
        session = SessionState()
        session.__post_init__()
        st.session_state[_SESSION_STATE_KEY] = session
    return st.session_state[_SESSION_STATE_KEY]


def reset_session_state() -> None:
    if _SESSION_STATE_KEY in st.session_state:
        del st.session_state[_SESSION_STATE_KEY]
    logger.info("🗑️ SessionState сброшен")