"""
Компонент: Компактный редактор JSON от LLM.
🔹 Только редактирование значений
🔹 Русские метки полей
🔹 Минимальные отступы
"""

import json
import streamlit as st
from pathlib import Path
from typing import Any

from ui.utils.components import error_handler, render_empty_state
from ui.utils.ui_hacks import add_compact_editor_styles
from ui.utils.json_editor_utils import (
    init_edit_state,
    render_editable_fields,
    collect_edited_values,
    handle_llm_json_save,
)


def render_llm_json_editor(
    file_id: str,
    file_service: Any,
    redis_client: Any,
    session_state,
    compact_mode: bool = True
) -> None:
    """Рендерит компактный редактор JSON с русскими метками."""
    if not file_service:
        st.error("⚠️ FileService не доступен")
        return

    if compact_mode:
        add_compact_editor_styles()

    with error_handler("llm_json_editor", "Ошибка загрузки JSON"):
        llm_dir = file_service.base_dir / file_id / "llm"
        json_file = llm_dir / f"{file_id}_llm.json"

        if not json_file.exists():
            render_empty_state("📭 JSON-файл ещё не создан")
            st.caption("💡 Файл появится после завершения LLM-обработки")
            return

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            st.error(f"❌ Ошибка парсинга JSON: {e}")
            return
        except Exception as e:
            st.error(f"❌ Ошибка чтения: {e}")
            return

        state_key = f"llm_edit_{file_id}"
        if state_key not in st.session_state:
            st.session_state[state_key] = init_edit_state(data)

        # 🔹 ФОРМА: ТОЛЬКО поля + кнопка "Сохранить"
        with st.form(key=f"llm_edit_form_{file_id}", border=False):
            st.caption("💡 Меняйте значения. Ключи редактировать нельзя. ▼ — раскрыть вложенное")

            render_editable_fields(
                data=data,
                prefix="",
                file_id=file_id,
                session_state=st.session_state,
                compact=compact_mode,
                max_depth=3
            )

            st.divider()
            submitted = st.form_submit_button("💾 Сохранить", type="primary", use_container_width=True)

            if submitted:
                edit_state = st.session_state.get("llm_edit_state", {})
                updated_data = collect_edited_values(data, edit_state)

                if handle_llm_json_save(file_id, json_file, updated_data, redis_client):
                    st.success("✅ Сохранено!")
                    _cleanup_and_navigate(session_state, file_id)
                    st.rerun()
                else:
                    st.error("❌ Не удалось сохранить")

        # 🔹 Кнопки ВНЕ формы (не работают внутри st.form)
        col_cancel, col_download = st.columns([1, 1])

        with col_cancel:
            if st.button("✖️ Отмена", key=f"cancel_{file_id}", use_container_width=True):
                _cleanup_and_navigate(session_state, file_id)
                st.rerun()

        with col_download:
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


def _cleanup_and_navigate(session_state, file_id: str) -> None:
    """Очистка состояния и навигация на главную."""
    state_key = f"llm_edit_{file_id}"
    if state_key in st.session_state:
        del st.session_state[state_key]
    if "llm_edit_state" in st.session_state:
        del st.session_state["llm_edit_state"]

    session_state.navigate("main")
    session_state.editing_file_index = None
    session_state.file_id = None