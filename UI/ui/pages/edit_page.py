# ui/pages/edit_page.py
"""
Страница редактирования JSON
"""
import streamlit as st
from typing import Any, Dict
from utils import setup_logger

logger = setup_logger("ui.pages.edit_page")


def render_edit_page(state: Any) -> None:
    """
    Рендерит страницу редактирования файла.

    Args:
        state: Объект состояния приложения
    """
    logger.info(f"Рендеринг страницы редактирования: индекс={state.editing_file_index}")

    st.title("✏️ Редактирование файла")

    file_index = state.editing_file_index
    file_name = state.file_data["Имя файла"][file_index]

    st.info(f"📄 Редактирование файла: **{file_name}**")
    st.subheader("📋 Данные документа")

    edited_values = {}
    _render_json_editor(state.json_data, edited_values)

    st.divider()
    _render_action_buttons(file_index, file_name, state, edited_values)

    if st.button("← Вернуться на главную страницу"):
        logger.debug("Пользователь нажал 'Вернуться на главную'")
        state.navigate("main")
        st.rerun()


def _render_json_editor(data: Dict, edited_values: Dict, prefix: str = "") -> None:
    """Рекурсивно рендерит редактор JSON"""
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            with st.expander(f"📁 {key}", expanded=False):
                _render_json_editor(value, edited_values, full_key)
        elif isinstance(value, list):
            with st.expander(f"📦 {key} (список)", expanded=False):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        with st.container(border=True):
                            st.markdown(f"**Элемент {i + 1}**")
                            _render_json_editor(item, edited_values, f"{full_key}[{i}]")
                    else:
                        edited_values[f"{full_key}[{i}]"] = st.text_input(
                            f"{full_key}[{i}]", value=str(item), key=f"input_{full_key}_{i}"
                        )
        else:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{key}**")
            with col2:
                edited_values[full_key] = st.text_input(
                    f"edit_{full_key}", value=str(value), key=f"txt_{full_key}", label_visibility="collapsed"
                )


def _render_action_buttons(
        file_index: int,
        file_name: str,
        state: Any,
        edited_values: Dict
) -> None:
    """Рендерит кнопки действий (Сохранить, Отмена, Сброс)"""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Сохранить", use_container_width=True, type="primary"):
            logger.info(f"Пользователь сохранил изменения файла {file_name}")
            state.add_log("ОК", f"Файл {file_name} отредактирован пользователем")
            state.add_log("ОК", f"Статус файла {file_name} изменен на 'Поправлен'")

            state.file_data["Статус"][file_index] = "🟣 Поправлен"
            st.success("✅ Данные сохранены! Статус файла изменен на 'Поправлен'")
            st.balloons()

            state.navigate("main")
            st.rerun()

    with col2:
        if st.button("❌ Отмена", use_container_width=True):
            logger.warning(f"Пользователь отменил редактирование файла {file_name}")
            state.add_log("ERROR", f"Редактирование файла {file_name} отменено пользователем")
            st.warning("⚠️ Изменения не сохранены")

            state.navigate("main")
            st.rerun()

    with col3:
        if st.button("🔄 Сбросить", use_container_width=True):
            logger.info(f"Пользователь сбросил JSON для файла {file_name}")
            state.json_data = state.get_default_json().copy()
            st.info("🔄 JSON сброшен к значениям по умолчанию")
            st.rerun()