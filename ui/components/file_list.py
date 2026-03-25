# ui/components/file_list.py
"""
Компонент: Список файлов в реестре.
"""

import streamlit as st
from typing import Any, List, Dict, Optional

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import (
    format_datetime_short,
    render_status_badge,
    truncate_filename
)
from ui.utils.components import error_handler, render_columns_config, render_action_button
from ui.utils.redis_helpers import safe_get_all_files

logger = setup_logger("ui.components.file_list")


def render_file_list(redis_client, file_service, session_state) -> None:
    """Рендерит таблицу файлов."""
    with error_handler("file_list", "Ошибка загрузки списка файлов"):
        files = safe_get_all_files(redis_client)

        if not files:
            st.info("ℹ️ Файлы пока не загружены. Ожидание новых файлов...")
            return

        # Заголовки
        cols = render_columns_config([2, 3, 2, 2, 2, 1])
        headers = ["ID", "Файл", "Статус", "Модуль", "Время", "Действия"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        st.divider()

        # Строки (последние файлы с учётом лимита)
        display_files = files[-UI_CONFIG["max_files_display"]:]
        for file_data in reversed(display_files):
            _render_file_row(file_data, redis_client, session_state)
            st.divider()


def _render_file_row(file_data: Dict[str, Any], redis_client, session_state) -> None:
    """Рендерит одну строку файла."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    status = file_data.get("status", "unknown")
    current_module = file_data.get("current_module", "-")
    created_at = format_datetime_short(file_data.get("created_at"))

    cols = render_columns_config([2, 3, 2, 2, 2, 1])

    cols[0].code(file_id[:12], language="text")  # Короткий ID
    cols[1].markdown(f"📄 {truncate_filename(filename)}")
    cols[2].markdown(render_status_badge(status))
    cols[3].markdown(f"`{current_module}`" if current_module else "-")
    cols[4].markdown(created_at)

    if render_action_button("📋", key=f"detail_{file_id}", help="Детали файла", use_container_width=True):
        _navigate_to_detail(file_id, file_data, session_state)


def _navigate_to_detail(file_id: str, file_data: Dict, session_state):
    """Навигация к деталям файла."""
    files = safe_get_all_files(session_state.redis_client)
    try:
        index = [f.get("file_id") for f in files].index(file_id)
        session_state.editing_file_index = index
        session_state.current_page = "detail"
        st.rerun()
    except ValueError:
        st.error("❌ Файл не найден")