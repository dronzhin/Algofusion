# app.py
import streamlit as st
from pages import get_page_renderer
from state.session_manager import SessionManager  # Импортируем инициализацию

# Инициализация сессии при запуске приложения
SessionManager.initialize_session()

# Настройка страницы
st.set_page_config(page_title="Мой OCR-анализатор", layout="wide")
st.title("🚀 Многофункциональный анализ файлов")

# Определение вкладок
TAB_CONFIG = {
    "Информация о файле": "file_info",
    "Выравнивание изображения": "image_rotation", 
    "Бинарное изображение": "binary_image",
}

# Создание вкладок
tabs = st.tabs(list(TAB_CONFIG.keys()))

# Динамический рендеринг вкладок
for tab, (tab_name, page_key) in zip(tabs, TAB_CONFIG.items()):
    with tab:
        render_page = get_page_renderer(page_key)
        render_page()