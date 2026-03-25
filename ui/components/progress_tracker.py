"""
Компонент: Трекер прогресса обработки.
"""

import streamlit as st
from typing import Dict, Any, List

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import calculate_module_progress, render_status_badge_safe
from ui.utils.components import error_handler, render_empty_state

logger = setup_logger("ui.components.progress_tracker")


def render_progress_tracker(redis_client) -> None:
    """
    Визуализация прогресса по файлам.

    Args:
        redis_client: Экземпляр RedisClient для получения данных
    """
    with error_handler("progress_tracker", "Не удалось отобразить прогресс"):
        # ← Получаем файлы внутри функции (просто и надёжно)
        try:
            if hasattr(redis_client, 'get_all_files'):
                files = redis_client.get_all_files()
            else:
                logger.warning(f"redis_client не имеет метода get_all_files: {type(redis_client)}")
                files = []
        except Exception as e:
            logger.error(f"Ошибка получения файлов: {e}")
            files = []

        # Фильтруем файлы в обработке (с защитой типов)
        processing_files = [
            f for f in files
            if isinstance(f, dict) and f.get("status") == "processing"
        ][:UI_CONFIG["max_processing_display"]]

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

    # Заголовок с именем файла
    st.markdown(f"**📄 {filename}** (`{file_id[:8]}...`)")

    # Прогресс-бар
    st.progress(progress / 100)

    # Статусы модулей с цветными бейджами
    status_line = "  ".join(status_texts)
    st.caption(status_line)