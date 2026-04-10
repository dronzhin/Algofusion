# ui/app.py
"""
Точка входа UI приложения Algofusion File Processor.
🔹 Автоматически запускает валидацию и очистку мёртвых записей при старте.
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
from ui.cache import get_redis_client_cached, run_startup_validation
from ui.pages.main_page import render_main_page

logger = setup_logger("ui.app")


# ============================================================================
# 4. ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    logger.info("🚀 Приложение запущено")

    from ui.utils.ui_hacks import hide_streamlit_navigation
    hide_streamlit_navigation()

    session = get_session_state()

    # Инициализация сервисов
    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    if session.settings is None:
        session.settings = get_settings()

    if session.file_service is None:
        from core.services.file_service import FileService
        session.file_service = FileService(session.settings.shared_files_path)

    # ========================================================================
    # 🔹 ОДНОРАЗОВАЯ ВАЛИДАЦИЯ ПРИ СТАРТЕ (кэшируется, не гоняется при rerun)
    # ========================================================================
    if not getattr(session, "_startup_validation_done", False):
        logger.info("⏳ Запуск проверки целостности файлов...")
        result = run_startup_validation(session.redis_client, session.file_service)
        session._startup_validation_done = True

        if result["cleaned"] > 0:
            st.toast(f"🧹 Удалено {result['cleaned']} мёртвых записей", icon="🗑️")
            logger.info(f"🧹 Стартовая очистка: удалено {result['cleaned']} записей")
        else:
            logger.debug("✅ Все записи в Redis соответствуют файлам на диске")

    # ========================================================================
    # 🔹 ОБРАБОТКА СОБЫТИЙ И РЕНДЕРИНГ
    # ========================================================================

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