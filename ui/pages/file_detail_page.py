#!/usr/bin/env python3
# ui/pages/file_detail_page.py
"""
Страница редактирования JSON от LLM.
Только редактор + сохранение + скачивание + возврат.
"""

import streamlit as st
from shared.utils.logger import setup_logger
from ui.utils.components import error_handler
from ui.utils.redis_helpers import safe_get_all_files
from ui.components.file_detail.llm_editor import render_llm_json_editor

logger = setup_logger("ui.pages.file_detail_page")


def render_file_detail_page(session_state) -> None:
    """Рендерит только редактор JSON."""
    with error_handler("file_detail_page", "Ошибка загрузки редактора"):
        redis_client = session_state.redis_client
        file_service = session_state.file_service
        file_id = getattr(session_state, "file_id", None)

        # 🔹 Валидация
        if not file_id or not redis_client or not file_service:
            st.error("❌ Файл не выбран")
            _render_back(session_state)
            return

        # 🔹 Проверка существования файла
        files = safe_get_all_files(redis_client)
        file_data = next((f for f in files if f.get("file_id") == file_id), None)

        if not file_data:
            st.error("❌ Файл не найден в реестре")
            _render_back(session_state)
            return

        # 🔹 Заголовок
        st.title("✏️ Редактор JSON")
        st.caption(f"📄 Файл: `{file_data.get('original_filename', file_id)}`")
        _render_back(session_state)
        st.divider()

        # 🔹 Редактор
        render_llm_json_editor(
            file_id=file_id,
            file_service=file_service,
            redis_client=redis_client,
            session_state=session_state,
            compact_mode=True
        )


def _render_back(session_state) -> None:
    """Кнопка возврата."""
    if st.button("← Назад к реестру", key="back_to_list", use_container_width=True):
        file_id = getattr(session_state, "file_id", None)
        if file_id:
            for key in list(st.session_state.keys()):
                if key.startswith(f"llm_edit_{file_id}") or key == "llm_edit_state":
                    del st.session_state[key]

        session_state.navigate("main")
        session_state.editing_file_index = None
        session_state.file_id = None
        st.rerun()