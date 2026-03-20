# ui/utils/streamlit_helpers.py
import logging
from typing import Optional
import streamlit as st

# Кэш логгеров для предотвращения дублирования хендлеров
_loggers = {}

class StreamlitLogHandler:
    """
    Хендлер для вывода логов прямо в интерфейс Streamlit.
    Используется для отладки в режиме реального времени.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def info(self, msg: str):
        self.logger.info(msg)
        st.info(msg)

    def success(self, msg: str):
        self.logger.info(f"✅ {msg}")
        st.success(msg)

    def warning(self, msg: str):
        self.logger.warning(f"⚠️ {msg}")
        st.warning(msg)

    def error(self, msg: str, exc: Optional[Exception] = None):
        error_msg = f"❌ {msg}"
        if exc:
            error_msg += f": {str(exc)}"
        self.logger.error(error_msg, exc_info=exc)
        st.error(error_msg)