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

    # Сайдбар с настройками
    _render_sidebar(session, redis_client)

    # Статистика (кэшированная, принимает redis_client)
    stats = get_file_stats_cached(redis_client)
    render_stats_panel(stats)

    st.divider()

    # Прогресс обработки (принимает redis_client, сам получает файлы)
    st.subheader("📈 Прогресс обработки")
    render_progress_tracker(redis_client)

    st.divider()

    # Реестр файлов (кэшированный, передаём готовый список)
    st.subheader("📄 Реестр файлов")
    files = get_files_from_redis_cached(redis_client, cache_key="files_list")
    # ✅ ИСПРАВЛЕНО: передаём files первым аргументом (соответствует сигнатуре render_file_list)
    render_file_list(files, session, file_service)

    # Обновление времени последнего запроса
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

        # Фильтры по статусу
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

        # Статус подключения к Redis
        st.subheader("📡 Статус")
        try:
            redis_client.client.ping()
            st.success("✅ Redis подключен")
        except:
            st.error("❌ Redis отключен")

        # ← ✅ ИСПРАВЛЕНО: Неблокирующий авто-рефреш
        if auto_refresh:
            import time

            # Инициализируем время последнего обновления, если нужно
            if "last_refresh_time" not in st.session_state:
                st.session_state.last_refresh_time = time.time()

            # Проверяем, прошло ли достаточно времени
            elapsed = time.time() - st.session_state.last_refresh_time
            if elapsed >= refresh_interval:
                st.session_state.last_refresh_time = time.time()
                st.rerun()  # ← Перезагружаем страницу БЕЗ блокировки
            else:
                # Показываем индикатор следующего обновления
                remaining = int(refresh_interval - elapsed)
                st.caption(f"🔄 След. обновление через {remaining}с")