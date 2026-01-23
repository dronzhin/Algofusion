# app.py

# === 1. ИМПОРТ И НАСТРОЙКА ЛОГИРОВАНИЯ ===
import os
from utils import setup_app_logger

# Настройка логгера до любых других импортов
APP_LOGGER = setup_app_logger(
    name="app",
    level=os.getenv("LOG_LEVEL", "DEBUG"),
    log_file=os.getenv("LOG_FILE", "./logs/app.log")
)

APP_LOGGER.info("=== Запуск приложения OCR-анализатора ===")

# === 2. ОСТАЛЬНЫЕ ИМПОРТЫ ===
import streamlit as st
from pages import get_page_renderer
from state import SessionManager

# === 3. ИНИЦИАЛИЗАЦИЯ ===
try:
    SessionManager.initialize_session()
    APP_LOGGER.info("Сессия успешно инициализирована")
except Exception as e:
    APP_LOGGER.error(f"Ошибка при инициализации сессии: {e}", exc_info=True)
    st.error("Не удалось инициализировать сессию. Обратитесь к администратору.")
    st.stop()

# === 4. UI ===
st.set_page_config(page_title="Мой OCR-анализатор", layout="wide")
st.title("🚀 Многофункциональный анализ файлов")

TAB_CONFIG = {
    "Информация о файле": "file_info",
    "Выравнивание изображения": "image_rotation",
    "Бинарное изображение": "binary_image",
}

APP_LOGGER.debug(f"Создание вкладок: {list(TAB_CONFIG.keys())}")
tabs = st.tabs(list(TAB_CONFIG.keys()))

# === 5. РЕНДЕРИНГ ВКЛАДОК ===
for tab, (tab_name, page_key) in zip(tabs, TAB_CONFIG.items()):
    with tab:
        APP_LOGGER.debug(f"Рендеринг вкладки: {tab_name} (ключ: {page_key})")
        try:
            render_page = get_page_renderer(page_key)
            render_page()
        except Exception as e:
            APP_LOGGER.error(f"Ошибка при рендеринге страницы '{page_key}': {e}", exc_info=True)
            st.error(f"⚠️ Ошибка при загрузке вкладки '{tab_name}'. Подробности в логах.")