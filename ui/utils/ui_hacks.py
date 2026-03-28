# ui/utils/ui_hacks.py
"""
Утилиты для скрытия элементов интерфейса Streamlit.
"""

import streamlit as st


def hide_streamlit_navigation():
    """Скрывает стандартную навигацию и лишние элементы Streamlit."""
    st.markdown("""
    <style>
        /* Скрыть навигацию в сайдбаре */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        /* Скрыть меню "⋮" в верхнем правом углу */
        #MainMenu {
            visibility: hidden;
        }

        /* Скрыть футер */
        footer {
            visibility: hidden;
        }

        /* Компенсировать отступ после скрытия навигации */
        .block-container {
            padding-top: 1rem;
        }

        /* Убрать лишние отступы у экспандеров в сайдбаре */
        .streamlit-expanderHeader {
            padding: 0.5rem 1rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # ui/utils/ui_hacks.py

def add_compact_file_list_styles():
    """Добавляет компактные стили для списка файлов."""
    st.markdown("""
    <style>
        /* Уменьшаем отступы между блоками в списке файлов */
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
            margin-top: -1rem !important;
        }

        /* Уменьшаем отступы внутри expander */
        div[data-testid="stExpander"] {
            margin-bottom: 0.5rem !important;
            padding: 0.2rem 0.5rem !important;
        }

        /* Уменьшаем отступы заголовка expander */
        div[data-testid="stExpander"] summary {
            padding: 0.3rem 0.5rem !important;
            margin-bottom: 0.3rem !important;
        }

        /* Уменьшаем отступы для колонок */
        .stColumns {
            margin-bottom: 0.3rem !important;
            gap: 0.5rem !important;
        }

        /* Уменьшаем отступы для кнопок */
        .stButton > button {
            padding: 0.3rem 0.5rem !important;
            min-height: 2.5rem !important;
            font-size: 0.85rem !important;
        }

        /* Уменьшаем отступы для divider */
        hr[data-testid="stDivider"] {
            margin: 0.5rem 0 !important;
        }

        /* Компактные метаданные */
        .stCaption {
            margin-bottom: 0.2rem !important;
            font-size: 0.75rem !important;
        }

        /* Убираем лишние отступы у markdown заголовков */
        h5, h6 {
            margin-bottom: 0.3rem !important;
            margin-top: 0.3rem !important;
        }
    </style>
    """, unsafe_allow_html=True)