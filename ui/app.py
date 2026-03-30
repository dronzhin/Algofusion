# ui/app.py
"""
Точка входа UI приложения Algofusion File Processor.
"""

import sys
from pathlib import Path
import streamlit as st

# ============================================================================
# 1. НАСТРОЙКА ПУТЕЙ
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# 2. STREAMLIT CONFIG (ПЕРВЫЙ st.* вызов!)
# ============================================================================

st.set_page_config(
    page_title="Algofusion File Processor",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# ============================================================================
# 3. ИМПОРТЫ
# ============================================================================

from shared.utils.logger import setup_logger
from shared.config.settings import get_settings
from ui.state import get_session_state
from ui.cache import get_redis_client_cached
from ui.pages.main_page import render_main_page

logger = setup_logger("ui.app")


# ============================================================================
# 4. ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция приложения."""
    logger.info("🚀 Приложение запущено")

    # Скрыть стандартную навигацию Streamlit
    from ui.utils.ui_hacks import hide_streamlit_navigation
    hide_streamlit_navigation()

    # Инициализация состояния
    session = get_session_state()

    # Инициализация сервисов (только если ещё не созданы)
    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    if session.settings is None:
        session.settings = get_settings()

    if session.file_service is None:
        from core.services.file_service import FileService
        session.file_service = FileService(session.settings.shared_files_path)

    # ========================================================================
    # 🔹 ОБРАБОТКА СОБЫТИЙ И РЕНДЕРИНГ
    # ========================================================================

    # Обработка событий Redis теперь происходит внутри render_main_page()
    # через вызов session.process_events() — не дублируем здесь!

    # Рендеринг страницы
    try:
        if session.current_page == "main":
            render_main_page(session)
        else:
            st.error(f"❌ Неизвестная страница: {session.current_page}")
            session.navigate("main")
            render_main_page(session)

    except Exception as e:
        logger.error(f"❌ Ошибка рендеринга страницы: {e}", exc_info=True)
        st.error(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()