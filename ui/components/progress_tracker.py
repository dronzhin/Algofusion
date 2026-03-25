# ui/components/progress_tracker.py
"""
Компонент: Трекер прогресса обработки.
"""

import streamlit as st
from typing import Dict, Any

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import calculate_module_progress
from ui.utils.components import error_handler, render_empty_state
from ui.utils.redis_helpers import safe_get_all_files

logger = setup_logger("ui.components.progress_tracker")


def render_progress_tracker(redis_client) -> None:
    """Визуализация прогресса по файлам."""
    with error_handler("progress_tracker", "Не удалось отобразить прогресс"):
        files = safe_get_all_files(redis_client)
        processing_files = [f for f in files if f.get("status") == "processing"][:UI_CONFIG["max_processing_display"]]

        if not processing_files:
            render_empty_state("Нет файлов в обработке")
            return

        for file_data in processing_files:
            _render_file_progress(file_data)


def _render_file_progress(file_data: Dict[str, Any]) -> None:
    """Рендерит прогресс одного файла."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")

    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    progress, status_texts = calculate_module_progress(completed, current)

    st.markdown(f"**📄 {filename}** (`{file_id[:8]}...`)")
    st.progress(progress / 100)
    st.caption(" | ".join(status_texts))