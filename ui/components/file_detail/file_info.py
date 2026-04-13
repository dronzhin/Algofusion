# ui/components/file_detail/file_info.py
import streamlit as st
from typing import Dict, Any
from ui.utils.formatters import format_datetime_full, format_file_size_human, render_status_badge, render_export_status_badge

def render_file_info_section(file_data: Dict[str, Any]) -> None:
    col1, col2, col3 = st.columns(3)
    with col1: _render_file_info_col(file_data)
    with col2: _render_status_col(file_data)
    with col3: _render_export_col(file_data)

def _render_file_info_col(file_data: Dict[str, Any]) -> None:
    st.markdown("### 📁 Основная информация")
    st.markdown(f"**ID:** `{file_data.get('file_id', 'unknown')}`")
    st.markdown(f"**Имя:** {file_data.get('original_filename', 'Unknown')}")
    st.markdown(f"**Тип:** `{file_data.get('file_type', 'unknown')}`")
    st.markdown(f"**Размер:** {format_file_size_human(file_data.get('file_size', 0))}")
    metadata = file_data.get('metadata', {})
    if metadata:
        with st.expander("📦 Метаданные", expanded=False):
            for key, value in metadata.items():
                st.markdown(f"**{key}:** {value}")

def _render_status_col(file_data: Dict[str, Any]) -> None:
    st.markdown("### 📊 Статус обработки")
    status = file_data.get("status", "unknown")
    st.markdown(f"**Статус:** {render_status_badge(status)}", unsafe_allow_html=True)
    current_module = file_data.get("current_module")
    st.markdown(f"**Модуль:** `{current_module}`" if current_module else "**Модуль:** —")
    st.markdown(f"**Создан:** {format_datetime_full(file_data.get('created_at'))}")
    st.markdown(f"**Обновлён:** {format_datetime_full(file_data.get('updated_at'))}")

def _render_export_col(file_data: Dict[str, Any]) -> None:
    st.markdown("### 📤 Экспорт в 1С")
    export_status = file_data.get("export_status", "pending")
    st.markdown(f"**Статус:** {render_export_status_badge(export_status)}", unsafe_allow_html=True)
    st.markdown(f"**Попыток:** {file_data.get('export_attempts', 0)}")
    if file_data.get("export_error"):
        st.error(f"❌ {file_data['export_error']}")