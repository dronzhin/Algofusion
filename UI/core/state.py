# core/state.py
from dataclasses import dataclass, field
from typing import Optional
import streamlit as st


@dataclass
class AppState:
    """Централизованное управление session_state"""

    current_page: str = "main"
    editing_file_index: Optional[int] = None
    json_data: dict = field(default_factory=dict)
    export_pending: Optional[int] = None
    export_logs: list = field(default_factory=list)

    # Фильтры
    filter_date: Optional[str] = None
    filter_accuracy_type: str = "manual"
    filter_accuracy_manual: int = 100
    filter_reset_counter: int = 0

    # Данные
    file_data: dict = field(default_factory=dict)

    def __post_init__(self):
        # Инициализация только если не в session_state
        for attr, value in self.__dict__.items():
            if attr not in st.session_state:
                st.session_state[attr] = value

    @classmethod
    def get(cls) -> "AppState":
        """Получение экземпляра состояния (синглтон через session_state)"""
        if "app_state" not in st.session_state:
            st.session_state.app_state = cls()
        return st.session_state.app_state

    def navigate(self, page: str, **kwargs):
        """Безопасная навигация между страницами"""
        self.current_page = page
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_log(self, status: str, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M")
        self.export_logs.append({"time": timestamp, "status": status, "msg": message})
        if len(self.export_logs) > 20:
            self.export_logs = self.export_logs[-20:]