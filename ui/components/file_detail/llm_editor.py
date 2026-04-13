# ui/components/file_detail/llm_editor.py
"""
Компонент: Редактор JSON от LLM.
"""

import json
import streamlit as st
from pathlib import Path
from typing import Any

from ui.utils.components import error_handler, render_empty_state
from ui.utils.json_editor_utils import init_edit_state, render_editable_fields, collect_edited_values, \
    handle_llm_json_save


def render_llm_editor_section(file_id: str, file_service: Any, redis_client: Any, session_state) -> None:
    """Рендерит редактор JSON от LLM."""
    if not file_service:
        st.error("⚠️ FileService не доступен")
        return

    with error_handler("llm_json_editor", "Ошибка загрузки JSON"):
        llm_dir = file_service.base_dir / file_id / "llm"
        json_file = llm_dir / f"{file_id}_llm.json"

        if not json_file.exists():
            render_empty_state("📭 JSON-файл от LLM ещё не создан")
            st.caption("💡 Файл появится после завершения этапа LLM-обработки")
            return

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            st.error(f"❌ Ошибка чтения: {e}")
            return

        state_key = f"llm_edit_{file_id}"
        if state_key not in st.session_state:
            st.session_state[state_key] = init_edit_state(data)

        with st.form(key=f"llm_edit_form_{file_id}"):
            st.caption("ℹ️ Изменяйте значения — ключи редактировать нельзя. Вложенные поля раскрываются.")
            st.divider()
            render_editable_fields(data=data, prefix="", file_id=file_id, session_state=st.session_state)
            st.divider()

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                submit = st.form_submit_button("💾 Сохранить изменения", type="primary", use_container_width=True)
                if submit:
                    updated_data = collect_edited_values(data, st.session_state[state_key])
                    if handle_llm_json_save(file_id, json_file, data, updated_data, redis_client):
                        st.success("✅ Изменения сохранены!")
                        session_state.current_page = "main"
                        session_state.editing_file_index = None
                        st.rerun()
                    else:
                        st.error("❌ Не удалось сохранить изменения")
            with col2:
                pass  # Кнопка "Назад" рендерится после формы

        # Кнопка "Назад" (вне формы)
        if st.button("← Назад без сохранения", key=f"back_{file_id}", use_container_width=True):
            if state_key in st.session_state:
                del st.session_state[state_key]
            session_state.current_page = "main"
            session_state.editing_file_index = None
            st.rerun()

        # Кнопка "Скачать"
        with open(json_file, "r", encoding="utf-8") as f:
            json_content = f.read()
        st.download_button(
            label="📥 Скачать JSON",
            data=json_content,
            file_name=f"{file_id}_llm.json",
            mime="application/json",
            key=f"download_{file_id}",
            use_container_width=True
        )