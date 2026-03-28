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
# 4. ОБРАБОТЧИК СОБЫТИЙ REDIS
# ============================================================================

def _process_redis_events(session) -> bool:
    """
    Обработка событий из Redis Pub/Sub (неблокирующая).
    Returns: True, если были обработаны события.
    """
    try:
        redis_client = session.redis_client
        if not redis_client:
            return False

        if session.pubsub is None:
            session.pubsub = redis_client.subscribe(["files:events", "1c:export"])

        message = session.pubsub.get_message(timeout=0.1)
        if message and message["type"] == "message":
            import json
            event = json.loads(message["data"])
            event_type = event.get("type", "unknown")
            filename = event.get("filename", "unknown")

            if event_type in ["file_uploaded", "module_completed", "export_completed", "file_error"]:
                status = "ERROR" if event_type == "file_error" else "ОК"
                icon = "❌" if event_type == "file_error" else "✅"
                session.add_log(status, f"{icon} {event_type}: {filename}")
                session.invalidate_cache()
                return True

    except Exception as e:
        logger.warning(f"⚠️ Ошибка обработки событий Redis: {e}")

    return False


# ============================================================================
# 5. ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция приложения."""
    logger.info("🚀 Приложение запущено")

    # Скрыть стандартную навигацию Streamlit
    from ui.utils.ui_hacks import hide_streamlit_navigation
    hide_streamlit_navigation()

    # Инициализация состояния
    session = get_session_state()

    # Инициализация сервисов
    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    settings = get_settings()
    session.settings = settings

    if session.file_service is None:
        from core.services.file_service import FileService
        session.file_service = FileService(settings.shared_files_path)

    # Обработка событий Redis
    _process_redis_events(session)

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