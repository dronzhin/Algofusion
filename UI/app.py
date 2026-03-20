# app.py
"""
Точка входа приложения Algofusion File Processor
"""
# 1. Streamlit и set_page_config - ПЕРВЫЙ st.* вызов!
import streamlit as st

st.set_page_config(
    page_title="Algofusion File Processor",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Теперь все остальные импорты
from utils import setup_logger
from core.state import AppState
from ui.pages.main_page import render_main_page
from ui.pages.edit_page import render_edit_page

# 3. Инициализация
logger = setup_logger("app")


def main():
    logger.info("Приложение запущено")
    state = AppState.get()

    if state.current_page == 'main':
        render_main_page(state)
    elif state.current_page == 'edit':
        render_edit_page(state)


if __name__ == "__main__":
    main()