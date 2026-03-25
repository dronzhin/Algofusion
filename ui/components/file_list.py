"""
Компонент: Список файлов в реестре.
"""

import streamlit as st
from typing import Any, List, Dict, Optional

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import (
    format_datetime_short,
    render_status_badge_safe,
    truncate_filename
)
from ui.utils.components import error_handler, render_columns_config, render_action_button

logger = setup_logger("ui.components.file_list")


def render_file_list(
    files: List[Dict[str, Any]],
    session_state: Any,
    file_service: Optional[Any] = None
) -> None:
    """
    Рендерит таблицу файлов.

    Args:
        files: Список файлов из Redis (уже полученный)
        session_state: Состояние сессии
        file_service: FileService (опционально, для будущих расширений)
    """
    with error_handler("file_list", "Ошибка отображения списка файлов"):
        if not files:
            st.info("ℹ️ Файлы пока не загружены. Ожидание новых файлов...")
            return

        # Заголовки таблицы
        cols = render_columns_config([2, 3, 2, 2, 2, 1])
        headers = ["ID", "Файл", "Статус", "Модуль", "Время", "Действия"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        st.divider()

        # Строки (последние файлы с учётом лимита, новые сверху)
        display_files = files[-UI_CONFIG["max_files_display"]:]
        for file_data in reversed(display_files):
            _render_file_row(file_data, session_state)
            st.divider()


def _render_file_row(
    file_data: Dict[str, Any],
    session_state: Any
) -> None:
    """Рендерит одну строку файла."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    status = file_data.get("status", "unknown")
    current_module = file_data.get("current_module", "-")
    created_at = format_datetime_short(file_data.get("created_at"))

    cols = render_columns_config([2, 3, 2, 2, 2, 1])

    # ID файла (короткая версия)
    cols[0].code(file_id[:12], language="text")

    # Имя файла (с обрезкой если длинное)
    cols[1].markdown(f"📄 {truncate_filename(filename)}")

    # Статус с цветным бейджем
    render_status_badge_safe(status, cols[2])

    # Текущий модуль обработки
    cols[3].markdown(f"`{current_module}`" if current_module else "-")

    # Время создания
    cols[4].markdown(created_at)

    # Кнопка перехода к деталям
    if render_action_button("📋", key=f"detail_{file_id}", help="Детали файла", use_container_width=True):
        _navigate_to_detail(file_id, file_data, session_state)


def _navigate_to_detail(
    file_id: str,
    file_data: Dict[str, Any],
    session_state: Any
) -> None:
    """
    Навигация к деталям файла.

    Args:
        file_id: ID файла для поиска
        file_data: Данные файла
        session_state: Состояние сессии
    """
    if session_state.redis_client:
        try:
            files = session_state.redis_client.get_all_files()
            index = [f.get("file_id") for f in files].index(file_id)
            session_state.editing_file_index = index
            session_state.current_page = "detail"
            st.rerun()
        except (ValueError, AttributeError) as e:
            logger.warning(f"Не удалось найти файл {file_id}: {e}")
            st.error("❌ Файл не найден")
    else:
        st.error("❌ Redis клиент не доступен")