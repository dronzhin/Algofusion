# pages/file_info.py
import streamlit as st
from services.file_service import FileService
from components import FilePreviewComponent
from state.session_manager import SessionManager  # Используем наш менеджер
from utils import get_file_metadata, get_file_icon
from pathlib import Path


def render_page():
    """
    Страница информации о файле с использованием SessionManager
    """
    st.subheader("📄 Анализ файла")

    # Очищаем результаты при загрузке нового файла
    if "last_uploaded_file" in st.session_state:
        current_file = st.session_state["last_uploaded_file"]
    else:
        current_file = None

    uploaded = st.file_uploader("Загрузите файл", key="main_file_uploader")

    # Очищаем состояние при новой загрузке
    if uploaded is not None and (current_file != uploaded.name):
        SessionManager.clear_all_results()
        st.session_state["last_uploaded_file"] = uploaded.name

    if uploaded is None:
        # Очищаем shared_file если файл удален
        if current_file is not None:
            SessionManager.clear_shared_file()
            st.session_state["last_uploaded_file"] = None
        return

    file_name = uploaded.name
    file_size = uploaded.size
    mime_type = uploaded.type
    file_ext = Path(file_name).suffix.lower()

    # Сохраняем файл в состояние через SessionManager
    file_info = {
        "name": file_name,
        "bytes": uploaded.getvalue(),
        "type": mime_type,
        "ext": file_ext
    }
    SessionManager.set_shared_file(file_info)

    # Используем универсальную функцию для отображения
    FilePreviewComponent.render(
        file_bytes=uploaded.getvalue(),
        file_type=mime_type,
        file_name=file_name,
        file_ext=file_ext,
        title="📥 Исходный файл",
        show_metadata=True
    )