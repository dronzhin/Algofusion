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