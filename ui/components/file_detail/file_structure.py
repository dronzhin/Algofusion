# ui/components/file_detail/file_structure.py
import streamlit as st
from typing import Any
from ui.utils.components import error_handler, render_empty_state

def render_file_structure_section(file_id: str, file_service: Any) -> None:
    if not file_service:
        render_empty_state("⚠️ FileService не доступен")
        return
    with error_handler("file_structure", "Ошибка получения структуры"):
        file_info = file_service.get_file_info(file_id)
        if not file_info:
            render_empty_state("⚠️ Информация о файле не найдена на диске")
            return
        for folder, info in file_info.get("directories", {}).items():
            with st.expander(f"📁 {folder} ({info.get('file_count', 0)} файлов)", expanded=False):
                st.caption(f"📍 `{info.get('path', '')}`")
                for filename in info.get("files", [])[:20]:
                    st.markdown(f"📄 `{filename}`")