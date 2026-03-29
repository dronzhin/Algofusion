# ui/pages/main_page.py
"""
Главная страница мониторинга файлов.
С оптимизациями производительности.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================

import time
import streamlit as st

from shared.utils.logger import setup_logger
from ui.state import SessionState, get_session_state
from ui.cache import get_files_from_redis_cached, get_file_stats_cached, CacheManager
from ui.components.file_list import render_file_list
from ui.components.stats_panel import render_stats_panel
from ui.components.progress_tracker import render_progress_tracker

logger = setup_logger("ui.pages.main_page")

# ← Ключи для st.session_state (авто-рефреш)
_KEY_AUTO_REFRESH = "_af_auto_refresh"
_KEY_REFRESH_INTERVAL = "_af_refresh_interval"
_KEY_LAST_REFRESH = "_af_last_refresh"
_KEY_CACHE_BUSTER = "_af_cache_buster"


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def render_main_page(session: SessionState) -> None:
    """Рендерит главную страницу мониторинга."""
    logger.info("Рендеринг главной страницы")

    # ← ✅ Обработка авто-рефреша (в НАЧАЛЕ, до любого рендеринга)
    _run_auto_refresh(session)

    redis_client = session.redis_client
    file_service = session.file_service

    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        return

    # Сайдбар
    _render_sidebar(session, redis_client)

    # Статистика (с уникальным ключом кэша)
    cache_key = st.session_state.get(_KEY_CACHE_BUSTER, "v1")
    stats = get_file_stats_cached(redis_client, _cache_key=cache_key)
    render_stats_panel(stats)

    st.divider()

    # Прогресс
    st.subheader("📈 Прогресс обработки")
    render_progress_tracker(redis_client)

    st.divider()

    # Реестр файлов (с уникальным ключом кэша)
    st.subheader("📄 Реестр файлов")
    files = get_files_from_redis_cached(redis_client, _cache_key=cache_key)
    render_file_list(files, session, file_service)

    session.update_refresh_time()


def _run_auto_refresh(session: SessionState) -> None:
    """
    Логика авто-рефреша — вызывается в начале render_main_page.
    Принимает session как аргумент!
    """
    # Читаем настройки из st.session_state
    enabled = st.session_state.get(_KEY_AUTO_REFRESH, True)
    if not enabled:
        return

    interval = st.session_state.get(_KEY_REFRESH_INTERVAL, 10)
    last = st.session_state.get(_KEY_LAST_REFRESH, 0.0)  # ← FIX: 0.0, не 0
    now = time.time()

    # Проверяем условие
    if now - last >= float(interval):
        # Обновляем таймер
        st.session_state[_KEY_LAST_REFRESH] = now

        # Обновляем cache_buster для инвалидации кэша
        new_key = f"v{now}"
        st.session_state[_KEY_CACHE_BUSTER] = new_key

        # Инвалидируем кэш Streamlit
        CacheManager.clear_data_cache()

        # Перезагружаем страницу
        st.rerun()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def _render_sidebar(session: SessionState, redis_client) -> None:
    """Рендерит боковую панель настроек."""
    with st.sidebar:
        st.header("⚙️ Настройки")

        # Авто-обновление
        enabled = st.toggle(
            "Автообновление",
            value=st.session_state.get(_KEY_AUTO_REFRESH, True)
        )
        st.session_state[_KEY_AUTO_REFRESH] = enabled

        # Интервал
        interval = st.slider(
            "Интервал (сек)",
            min_value=5,
            max_value=60,
            value=int(st.session_state.get(_KEY_REFRESH_INTERVAL, 10))
        )
        st.session_state[_KEY_REFRESH_INTERVAL] = float(interval)

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

        # Статус Redis
        st.subheader("📡 Статус")
        try:
            redis_client.client.ping()
            st.success("✅ Redis подключен")
        except:
            st.error("❌ Redis отключен")

        # Индикатор авто-рефреша
        if enabled:
            last = st.session_state.get(_KEY_LAST_REFRESH, time.time())
            elapsed = time.time() - last
            remaining = max(0, int(interval - elapsed))
            st.caption(f"🔄 Авто-обновление: через {remaining}с")