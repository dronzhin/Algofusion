"""
Главная страница мониторинга файлов.
С оптимизациями производительности.
"""

import streamlit as st
from shared.utils.logger import setup_logger
from ui.state import SessionState
from ui.cache import get_files_from_redis_cached, get_file_stats_cached, CacheManager
from ui.components.file_list import render_file_list
from ui.components.stats_panel import render_stats_panel
from ui.components.progress_tracker import render_progress_tracker

logger = setup_logger("ui.pages.main_page")


def render_main_page(session: SessionState) -> None:
    """Рендерит главную страницу мониторинга."""
    logger.info("Рендеринг главной страницы")

    redis_client = session.redis_client
    file_service = session.file_service

    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        return

    # Сайдбар
    _render_sidebar(session, redis_client)

    # Статистика (кэшированная)
    stats = get_file_stats_cached(redis_client)
    render_stats_panel(stats)

    st.divider()

    # Прогресс обработки
    st.subheader("📈 Прогресс обработки")
    render_progress_tracker(redis_client)

    st.divider()

    # Реестр файлов (кэшированный)
    st.subheader("📄 Реестр файлов")
    files = get_files_from_redis_cached(redis_client, cache_key="files_list")
    render_file_list(files, session, file_service)

    # Обновление времени
    session.update_refresh_time()


def _render_sidebar(session: SessionState, redis_client) -> None:
    """Рендерит боковую панель настроек."""
    with st.sidebar:
        st.header("⚙️ Настройки")

        # Автообновление
        auto_refresh = st.toggle("Автообновление", value=True)

        # Интервал обновления
        refresh_interval = st.slider("Интервал (сек)", min_value=5, max_value=60, value=10)

        st.divider()

        # Фильтры
        st.subheader("🔍 Фильтры")

        status_filter = st.multiselect(
            "Статус",
            ["uploaded", "processing", "completed", "failed", "exported"],
            default=session.get_filter("status", [])
        )
        session.set_filter("status", status_filter)

        st.divider()

        # Кнопки действий
        if st.button("🔄 Обновить сейчас", use_container_width=True):
            CacheManager.clear_data_cache()
            session.invalidate_cache()
            st.rerun()

        if st.button("🧹 Очистить кэш", use_container_width=True):
            CacheManager.clear_all()
            st.success("✅ Кэш очищен")
            st.rerun()

        st.divider()

        # Статус подключения
        st.subheader("📡 Статус")
        try:
            redis_client.client.ping()
            st.success("✅ Redis подключен")
        except:
            st.error("❌ Redis отключен")

        # Автообновление
        if auto_refresh:
            import time
            time.sleep(refresh_interval)
            st.rerun()