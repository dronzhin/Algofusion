# ui/components/file_list.py
"""
Компонент: Список файлов в реестре.
"""

import streamlit as st
from typing import Any, List, Dict
from shared.utils.logger import setup_logger
from ui.components.status_badge import render_status_badge

logger = setup_logger("ui.components.file_list")


def render_file_list(redis_client, file_service) -> None:
    """Рендерит таблицу файлов."""
    try:
        files = redis_client.get_all_files()

        if not files:
            st.info("ℹ️ Файлы пока не загружены. Ожидание новых файлов...")
            return

        # Заголовки
        cols = st.columns([2, 3, 2, 2, 2, 1])
        headers = ["ID", "Файл", "Статус", "Модуль", "Время", "Действия"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        st.divider()

        # Строки (последние 50 файлов)
        for file_data in reversed(files[-50:]):
            _render_file_row(file_data, redis_client)
            st.divider()

    except Exception as e:
        logger.error(f"Ошибка рендеринга списка файлов: {e}")
        st.error(f"❌ Ошибка загрузки списка файлов: {e}")


def _render_file_row(file_data: Dict[str, Any], redis_client) -> None:
    """Рендерит одну строку файла."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    status = file_data.get("status", "unknown")
    current_module = file_data.get("current_module", "-")
    created_at = file_data.get("created_at", "")[:16] if file_data.get("created_at") else "-"

    cols = st.columns([2, 3, 2, 2, 2, 1])

    # ID
    cols[0].code(file_id, language="text")

    # Имя файла
    cols[1].markdown(f"📄 {filename}")

    # Статус
    cols[2].markdown(render_status_badge(status))

    # Текущий модуль
    cols[3].markdown(f"`{current_module}`" if current_module else "-")

    # Время создания
    cols[4].markdown(f"{created_at}")

    # Кнопка деталей
    if cols[5].button("📋", key=f"detail_{file_id}", help="Детали файла", use_container_width=True):
        # Находим индекс файла в списке
        files = redis_client.get_all_files()
        try:
            index = [f.get("file_id") for f in files].index(file_id)
            st.session_state.editing_file_index = index
            st.session_state.current_page = "detail"
            st.rerun()
        except ValueError:
            st.error("❌ Файл не найден")