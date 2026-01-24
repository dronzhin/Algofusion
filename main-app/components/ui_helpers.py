# components/ui_helpers.py
import streamlit as st
from typing import Dict, List, Optional


def show_unsupported_file_error(
        file_info: Dict[str, str],
        supported_formats: Optional[List[str]] = None,
        operation_name: str = "обработка"
):
    ext = file_info.get("ext", "неизвестно")
    name = file_info.get("name", "файл")
    mime = file_info.get("type", "неизвестно")

    st.error(f"❌ Формат файла '{ext}' не поддерживается для {operation_name}")

    if supported_formats:
        formats_str = ", ".join(sorted(set(supported_formats)))
        st.info(f"Поддерживаются только: {formats_str}")

    st.markdown(f"""
    **Текущий файл:** {name}  
    **Тип:** `{mime}`  
    **Расширение:** `{ext}`
    """)