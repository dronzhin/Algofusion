# ui/components/progress_tracker.py
"""
Компонент: Трекер прогресса обработки.
"""

import streamlit as st
from typing import Dict, Any, List
from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.progress_tracker")


def render_progress_tracker(redis_client) -> None:
    """Визуализация прогресса по файлам."""
    try:
        files = redis_client.get_all_files()

        # Показываем только файлы в обработке (максимум 10)
        processing_files = [f for f in files if f.get("status") == "processing"][:10]

        if not processing_files:
            st.info("ℹ️ Нет файлов в обработке")
            return

        for file_data in processing_files:
            _render_file_progress(file_data)

    except Exception as e:
        logger.error(f"Ошибка рендеринга прогресса: {e}")
        st.warning("⚠️ Не удалось отобразить прогресс")


def _render_file_progress(file_data: Dict[str, Any]) -> None:
    """Рендерит прогресс одного файла."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    modules = ["preprocess", "ocr", "llm", "export"]
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    st.markdown(f"**📄 {filename}** (`{file_id[:8]}...`)")

    progress = 0
    status_text = []

    for module in modules:
        if module in completed:
            progress += 25
            status_text.append(f"✅ {module}")
        elif current == module:
            status_text.append(f"🔄 {module}")
        else:
            status_text.append(f"⏳ {module}")

    st.progress(progress / 100)
    st.caption(" | ".join(status_text))