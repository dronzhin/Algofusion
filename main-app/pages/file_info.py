# pages/file_info.py
import streamlit as st
import logging
from services import FileService
from components import FilePreviewComponent
from state import SessionManager
from utils import get_file_metadata, get_file_icon
from pathlib import Path

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")

def render_page():
    """
    Страница информации о файле с использованием SessionManager
    """
    logger.debug("Рендеринг страницы 'Информация о файле'")
    st.subheader("📄 Анализ файла")

    # Получаем текущее имя файла из сессии
    current_file = st.session_state.get("last_uploaded_file")
    logger.debug(f"Текущий загруженный файл в сессии: {current_file}")

    uploaded = st.file_uploader("Загрузите файл", key="main_file_uploader")

    # Очищаем состояние при новой загрузке
    if uploaded is not None:
        logger.debug(f"Пользователь загрузил файл: {uploaded.name}")
        if current_file != uploaded.name:
            logger.info(f"Обнаружен новый файл '{uploaded.name}' → очистка предыдущих результатов")
            SessionManager.clear_all_results()
            st.session_state["last_uploaded_file"] = uploaded.name
        else:
            logger.debug("Тот же файл повторно загружен — пропуск очистки")
    else:
        # Файл удалён или не загружен
        if current_file is not None:
            logger.info("Файл удалён пользователем → очистка shared_file")
            SessionManager.clear_shared_file()
            st.session_state["last_uploaded_file"] = None
        return

    # Подготавливаем метаданные
    file_name = uploaded.name
    mime_type = uploaded.type
    file_ext = Path(file_name).suffix.lower()

    try:
        file_info = {
            "name": file_name,
            "bytes": uploaded.getvalue(),
            "type": mime_type,
            "ext": file_ext
        }
        SessionManager.set_shared_file(file_info)
        logger.info(f"Файл сохранён в сессию: {file_name} ({mime_type}, {len(file_info['bytes'])} байт)")
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла в сессию: {e}", exc_info=True)
        st.error("Не удалось обработать загруженный файл. Проверьте логи.")
        return

    # Отображаем превью
    try:
        FilePreviewComponent.render(
            file_bytes=uploaded.getvalue(),
            file_type=mime_type,
            file_name=file_name,
            file_ext=file_ext,
            title="📥 Исходный файл",
            show_metadata=True
        )
        logger.debug("Превью файла успешно отображено")
    except Exception as e:
        logger.error(f"Ошибка при отображении превью: {e}", exc_info=True)
        st.warning("Не удалось отобразить превью файла.")