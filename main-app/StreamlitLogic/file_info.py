import streamlit as st
from pathlib import Path
from StreamlitLogic.file_renderer import render_file_preview

def render_file_info():
    """
    Основная точка входа.
    Загружает файл и делегирует обработку в зависимости от типа.
    Сохраняет файл в st.session_state для других вкладок.
    """
    st.subheader("📄 Анализ файла")
    uploaded = st.file_uploader("Загрузите файл", key="main_file_uploader")

    # Очищаем состояние при новой загрузке
    if uploaded is not None and (st.session_state.get("last_uploaded_file") != uploaded.name):
        st.session_state["shared_file"] = None
        st.session_state["last_uploaded_file"] = uploaded.name

    if uploaded is None:
        # Очищаем shared_file если файл удален
        st.session_state["shared_file"] = None
        return

    file_name = uploaded.name
    file_size = uploaded.size
    mime_type = uploaded.type
    file_ext = Path(file_name).suffix.lower()

    # Сохраняем файл в состояние для других вкладок
    st.session_state["shared_file"] = {
        "name": file_name,
        "bytes": uploaded.getvalue(),
        "type": mime_type,
        "ext": file_ext
    }

    # Используем универсальную функцию для отображения
    render_file_preview(
        file_bytes=uploaded.getvalue(),
        file_type=mime_type,
        file_name=file_name,
        file_ext=file_ext,
        title="📥 Исходный файл",
        show_metadata=True
    )