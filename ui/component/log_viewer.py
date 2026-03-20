# ui/components/log_viewer.py
"""
Компонент: Просмотрщик логов.
"""

import streamlit as st
from typing import List, Dict
from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.log_viewer")


def render_log_viewer(logs: List[Dict[str, str]], title: str = "📋 Журнал событий") -> None:
    """Отображает список логов."""
    try:
        with st.container(border=True):
            st.markdown(f"### {title}")

            if not logs:
                st.info("ℹ️ Логи пока пустые")
                return

            # Показываем последние 20 логов
            for log in logs[-20:]:
                _render_log_line(log)

    except Exception as e:
        logger.error(f"Ошибка рендеринга логов: {e}")


def _render_log_line(log: Dict[str, str]) -> None:
    """Рендерит одну строку лога."""
    timestamp = log.get("time", "??:??:??")
    status = log.get("status", "INFO")
    message = log.get("msg", "")

    if status == "ОК":
        color = "#28a745"
        badge = "✅"
    elif status == "ERROR":
        color = "#dc3545"
        badge = "❌"
    elif status == "WARNING":
        color = "#ffc107"
        badge = "⚠️"
    else:
        color = "#6c757d"
        badge = "ℹ️"

    html = f"""
    <div style="
        font-family: monospace;
        margin-bottom: 6px;
        font-size: 12px;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 4px;
    ">
        <span style="color: #888;">{timestamp}</span> 
        <span style="color: {color}; font-weight: bold;">{badge} {status}</span> 
        <span style="color: #333;">{message}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)