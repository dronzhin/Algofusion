# ui/pages/main_page.py
"""
Главная страница мониторинга файлов.
Оркестрация компонентов + управление автообновлением.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.utils.logger import setup_logger
from shared.config.settings import get_settings
from ui.state import SessionState, get_session_state
from ui.cache import get_files_from_redis_cached, get_file_stats_cached

# Компоненты
from ui.components.stats_panel import render_stats_panel
from ui.components.log_viewer import render_log_viewer
from ui.components.file_list import render_file_list
from ui.components.refresh_settings import render_refresh_settings, get_refresh_config

logger = setup_logger("ui.pages.main_page")


def render_main_page(session: SessionState) -> None:
    """Оркестрация главной страницы."""
    logger.info("📄 Рендеринг главной страницы")

    # Сначала рендерим сайдбар
    render_sidebar(session)

    # Проверка инициализации сервисов
    redis_client = session.redis_client
    file_service = session.file_service

    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        return
    if not file_service:
        st.error("❌ FileService не инициализирован")
        return

    # 🔁 Автообновление
    auto_refresh_enabled, auto_refresh_interval_sec = get_refresh_config(session)

    if auto_refresh_enabled:
        auto_refresh_interval_ms = auto_refresh_interval_sec * 1000
        st_autorefresh(
            interval=auto_refresh_interval_ms,
            limit=None,
            key="main_page_auto_refresh",
            debounce=True
        )

    # ========================================================================
    # 🔝 ВЕРХНЯЯ ПАНЕЛЬ: Логи + Статистика (две колонки)
    # ========================================================================

    # Создаём две колонки: логи шире (3 части), статистика уже (2 части)
    log_col, stats_col = st.columns([3, 2], gap="medium")

    with log_col:
        # 📋 Журнал событий
        logs = session.get_logs(limit=10)  # ← меньше записей, чтобы не растягивать
        render_log_viewer(
            logs=logs,
            title="📋 Журнал событий",
            show_pending_warning=session.pending_events,
            on_clear=session.clear_logs,
            limit=10  # ← компактный режим
        )

    with stats_col:
        # 📈 Статистика обработки
        stats = get_file_stats_cached(redis_client, _cache_key=session.cache_buster)
        render_stats_panel(stats, show_progress=True)

    st.divider()  # Разделитель между верхней панелью и списком файлов

    # ========================================================================
    # 📄 НИЖНЯЯ ЧАСТЬ: Реестр файлов
    # ========================================================================
    st.subheader("📄 Реестр файлов")

    # Панель управления списком
    col1, col2 = st.columns([4, 1])
    with col1:
        status_text = "🟢 Авто" if auto_refresh_enabled else "⏸️ Пауза"
        st.caption(f"🔄 {status_text} | {auto_refresh_interval_sec:.0f}с | Кэш: 30с")
    with col2:
        if st.button("🔄 Обновить", key="refresh_files_btn", use_container_width=True, type="primary"):
            session.invalidate_cache()
            st.rerun()

    # Callbacks для интерактивных действий
    def _on_detail(file_id: str):
        session.navigate("detail", file_id=file_id)
        st.rerun()

    def _on_retry(file_id: str):
        if file_service.retry_processing(file_id):
            session.invalidate_cache()
            st.success("✅ Запущена повторная обработка")
            st.rerun()

    def _on_delete(file_id: str):
        if file_service.delete_file(file_id):
            session.invalidate_cache()
            st.success("✅ Файл удалён")
            st.rerun()

    # Загрузка и рендер списка файлов
    files = get_files_from_redis_cached(redis_client, _cache_key=session.cache_buster)
    render_file_list(
        files=files,
        session_state=session,
        mode="cards",
        on_detail=_on_detail,
        on_retry=_on_retry,
        on_delete=_on_delete
    )

    session.update_refresh_time()


def render_sidebar(session: SessionState) -> None:
    """Рендерит боковую панель настроек."""
    with st.sidebar:
        st.header("⚙️ Настройки")

        # Автообновление (settings берётся из session внутри компонента)
        render_refresh_settings(session, key_prefix="main")
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

        # Статус системы
        st.subheader("📡 Статус")
        try:
            if hasattr(session.redis_client, 'client') and session.redis_client.client:
                session.redis_client.client.ping()
                st.success("✅ Redis подключен")
            else:
                st.warning("⚠️ Redis клиент не инициализирован")
        except Exception as e:
            st.error(f"❌ Redis: {e}")

        st.divider()
        # Версия и окружение тоже из session.settings
        settings = session.settings if hasattr(session, "settings") and session.settings else get_settings()
        st.caption(f"📦 Algofusion v{settings.app_version}")
        st.caption(f"🌐 {settings.environment.upper()}")