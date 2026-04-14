# ui/utils/ui_hacks.py
"""
Утилиты для скрытия элементов и компактных стилей Streamlit.
"""

import streamlit as st


def hide_streamlit_navigation():
    """Скрывает стандартную навигацию Streamlit."""
    st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)


def add_compact_file_list_styles():
    """Компактные стили для списка файлов."""
    st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] { margin-top: -1rem !important; }
        div[data-testid="stExpander"] { margin-bottom: 0.5rem !important; padding: 0.2rem 0.5rem !important; }
        div[data-testid="stExpander"] summary { padding: 0.3rem 0.5rem !important; }
        .stColumns { margin-bottom: 0.3rem !important; gap: 0.5rem !important; }
        .stButton > button { padding: 0.3rem 0.5rem !important; font-size: 0.85rem !important; }
        hr[data-testid="stDivider"] { margin: 0.5rem 0 !important; }
        .stCaption { margin-bottom: 0.2rem !important; font-size: 0.75rem !important; }
        h5, h6 { margin: 0.3rem 0 !important; }
    </style>
    """, unsafe_allow_html=True)


def add_compact_editor_styles():
    """
    Единая функция для компактных стилей редактора.
    🔹 Заменяет add_json_editor_styles и add_russian_editor_styles
    """
    st.markdown("""
    <style>
        /* Контейнеры формы */
        [data-testid="stForm"] { padding: 0 !important; }

        /* Экспандеры */
        .stExpander { 
            margin: 2px 0 !important; 
            border: 1px solid #e0e0e0 !important; 
            border-radius: 4px !important;
        }
        .stExpanderHeader { padding: 4px 8px !important; font-size: 0.9rem !important; }
        .stExpanderHeader:hover { background-color: #f5f5f5 !important; }

        /* Поля ввода */
        .stTextInput input, .stTextArea textarea {
            font-size: 0.9rem !important;
            padding: 4px 8px !important;
        }
        .stTextArea textarea { min-height: 60px !important; }

        /* Чекбоксы и переключатели */
        .stCheckbox { margin: 2px 0 !important; }
        .stCheckbox label { font-size: 0.9rem !important; }

        /* Кнопки */
        .stButton > button {
            font-size: 0.9rem !important;
            padding: 6px 12px !important;
        }

        /* Текст и заголовки */
        .stMarkdown, .stCaption { line-height: 1.3 !important; }
        .section-header { margin: 4px 0 !important; font-size: 1rem !important; font-weight: 600; }

        /* Разделители */
        hr { margin: 4px 0 !important; }

        /* Русские метки — визуальный акцент */
        .ru-label { font-weight: 600; }
        .field-key-hint { font-size: 0.75rem; color: #666; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)