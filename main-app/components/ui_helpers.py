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

def show_download_button(data: bytes, file_name: str, mime_type: str, label: str = "Скачать", key: str = None):
    """
    Универсальная кнопка для скачивания данных.

    Args:
        data (bytes): Байтовые данные файла.
        file_name (str): Имя файла для скачивания.
        mime_type (str): MIME-тип файла.
        label (str): Текст на кнопке.
        key (str): Уникальный ключ для Streamlit session_state.
    """
    st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=mime_type,
        key=key
    )

def select_page_number_ui(
    page_count: int,
    min_value: int = 1,
    max_value: int = None,
    initial_value: int = 1,
    key_suffix: str = ""
) -> int:
    """
    Универсальный UI-элемент для выбора номера страницы.

    Args:
        page_count (int): Общее количество страниц (используется, если max_value не задан).
        min_value (int): Минимальное значение.
        max_value (int): Максимальное значение. Если None, используется page_count.
        initial_value (int): Начальное значение.
        key_suffix (str): Суффикс для ключа session_state, чтобы избежать коллизий.

    Returns:
        int: Выбранный номер страницы (1-indexed).
    """
    max_val = max_value if max_value is not None else page_count
    initial_val = min(max(min_value, initial_value), max_val)

    page_num = st.number_input(
        "Номер страницы",
        min_value=min_value,
        max_value=max_val,
        value=initial_val,
        step=1,
        key=f"page_selector_{key_suffix}"
    )
    return page_num