#!/usr/bin/env python3
"""
Страница деталей файла.
Тонкий слой оркестрации компонентов.
"""

import streamlit as st
from shared.utils.logger import setup_logger
from ui.utils.components import error_handler
from ui.utils.redis_helpers import safe_get_all_files
from ui.components.file_detail import (
    render_file_info_section,
    render_progress_section,
    render_history_section,
    render_file_structure_section,
    render_llm_editor_section,
    render_actions_section,
)

logger = setup_logger("ui.pages.file_detail_page")


def render_file_detail_page(session_state) -> None:
    """Оркестрирует рендеринг страницы деталей файла."""
    with error_handler("file_detail_page", "Ошибка загрузки деталей"):
        # Валидация
        file_index = session_state.editing_file_index
        redis_client = session_state.redis_client
        file_service = session_state.file_service

        if file_index is None or not redis_client:
            st.error("❌ Файл не выбран");
            _render_back(session_state);
            return

        files = safe_get_all_files(redis_client)
        if file_index is None or file_index >= len(files):
            st.error("❌ Файл не найден");
            _render_back(session_state);
            return

        file_data = files[file_index]
        file_id = file_data.get("file_id")
        logger.info(f"Рендеринг деталей: {file_id}")

        # Заголовок
        st.title("📋 Детали файла")
        _render_back(session_state)
        st.divider()

        # Секции
        render_file_info_section(file_data)
        st.divider()
        render_progress_section(file_data)
        st.divider()
        render_history_section(file_data)
        st.divider()
        render_file_structure_section(file_id, file_service)
        st.divider()
        render_llm_editor_section(file_id, file_service, redis_client, session_state)
        st.divider()
        render_actions_section(file_id, file_data, redis_client)


def _render_back(session_state) -> None:
    """Кнопка возврата."""
    if st.button("← Вернуться к реестру", key="back_to_list"):
        session_state.update({"current_page": "main", "editing_file_index": None})
        st.rerun()