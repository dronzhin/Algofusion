# ui/app.py
"""
Точка входа UI приложения Algofusion File Processor.
С оптимизациями производительности и вынесенным состоянием.
"""

# ============================================================================
# 1. СТАНДАРТНЫЕ ИМПОРТЫ (без st.*)
# ============================================================================
import sys
from pathlib import Path

# Настройка путей
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# 2. STREAMLIT И set_page_config - ПЕРВЫЙ st.* вызов!
# ============================================================================
import streamlit as st

st.set_page_config(
    page_title="Algofusion File Processor",
    page_icon="📂",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/algofusion',
        'Report a bug': 'https://github.com/algofusion/issues',
        'About': "# Algofusion File Processor v0.1.0"
    }
)

# ============================================================================
# 3. ВСЕ ОСТАЛЬНЫЕ ИМПОРТЫ
# ============================================================================
from shared.utils.logger import setup_logger
from shared.config.settings import get_settings
from ui.state import get_session_state, SessionState
from ui.cache import (
    get_redis_client_cached,
    CacheManager
)
from ui.pages.main_page import render_main_page
from ui.pages.file_detail_page import render_file_detail_page

# Инициализация логгера
logger = setup_logger("ui.app")


# ============================================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def _process_redis_events(session: SessionState):
    """Обработка событий из Redis Pub/Sub (неблокирующая)."""
    try:
        redis_client = session.redis_client
        if not redis_client:
            return

        if session.pubsub is None:
            session.pubsub = redis_client.subscribe(["files:events", "1c:export"])

        message = session.pubsub.get_message(timeout=0.1)
        if message and message["type"] == "message":
            import json
            event = json.loads(message["data"])
            event_type = event.get("type", "unknown")

            # Обработка событий
            if event_type == "file_uploaded":
                session.add_log("ОК", f"📁 Новый файл: {event.get('filename')}")
                CacheManager.clear_data_cache()  # Инвалидация кэша
            elif event_type == "module_completed":
                session.add_log("ОК", f"✅ Модуль {event.get('module')} завершён")
                CacheManager.clear_data_cache()
            elif event_type == "file_error":
                session.add_log("ERROR", f"❌ Ошибка: {event.get('error')}")
            elif event_type == "export_completed":
                session.add_log("ОК", f"📤 Экспорт в 1С завершён")
                CacheManager.clear_data_cache()

    except Exception as e:
        logger.warning(f"Ошибка обработки событий Redis: {e}")


def _render_header(session: SessionState):
    """Рендерит заголовок приложения."""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("📂 Algofusion File Processor")

    with col2:
        st.metric("Время работы", session.get_uptime())

    with col3:
        if session.last_refresh:
            st.caption(f"Обновлено: {session.last_refresh.strftime('%H:%M:%S')}")


def _render_footer():
    """Рендерит футер приложения."""
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("© 2025 Algofusion")

    with col2:
        st.caption(f"Версия: {get_settings().log_level}")

    with col3:
        if st.button("🗑️ Очистить кэш", key="clear_cache_btn"):
            CacheManager.clear_all()
            st.success("✅ Кэш очищен")
            st.rerun()


# ============================================================================
# 5. ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция приложения."""
    logger.info("Приложение запущено")

    # Инициализация состояния
    session = get_session_state()

    # Инициализация сервисов (кэшированная)
    if session.redis_client is None:
        session.redis_client = get_redis_client_cached()

    settings = get_settings()
    session.settings = settings

    from core.services.file_service import FileService
    if session.file_service is None:
        session.file_service = FileService(settings.shared_files_path)

    # Обработка событий Redis
    _process_redis_events(session)

    # Заголовок
    _render_header(session)

    # Маршрутизация
    try:
        if session.current_page == "main":
            render_main_page(session)
        elif session.current_page == "detail":
            render_file_detail_page(session)
        else:
            st.error(f"❌ Неизвестная страница: {session.current_page}")
            session.navigate("main")
            render_main_page(session)
    except Exception as e:
        logger.error(f"Ошибка рендеринга страницы: {e}", exc_info=True)
        st.error(f"❌ Критическая ошибка: {e}")

    # Футер
    _render_footer()


if __name__ == "__main__":
    main()