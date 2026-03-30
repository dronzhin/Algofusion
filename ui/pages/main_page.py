# ui/pages/main_page.py
"""
Главная страница мониторинга файлов.
Оркестрация компонентов + управление автообновлением.
"""

# Standard library
from datetime import datetime, timezone
from typing import Optional, Callable

# Third-party
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Shared
from shared.utils.logger import setup_logger
from shared.config.settings import get_settings

# UI state & cache
from ui.state import SessionState, get_session_state
from ui.cache import get_files_from_redis_cached, get_file_stats_cached

# Components (только публичные функции!)
from ui.components.stats_panel import render_stats_panel
from ui.components.log_viewer import render_log_viewer
from ui.components.file_list import render_file_list
from ui.components.refresh_settings import render_refresh_settings, get_refresh_config

logger = setup_logger("ui.pages.main_page")


def render_main_page(session: SessionState) -> None:
    """
    Оркестрация главной страницы.

    Компонует: сайдбар, статистику, логи и список файлов.
    """
    logger.info("📄 Рендеринг главной страницы")

    # ========================================================================
    # 🔹 ОБРАБОТКА СОБЫТИЙ ОТ ПРОЦЕССОРА (добавляет логи в session)
    # ========================================================================
    try:
        session.process_events()
    except AttributeError as e:
        # Если атрибуты ещё не инициализированы — игнорируем на первом рендере
        logger.debug(f"⚠️ Пропуск обработки событий (сессия инициализируется): {e}")

    # ========================================================================
    # 🔹 СТИЛИ И САЙДБАР
    # ========================================================================

    # Применяем компактные стили для списка файлов
    from ui.utils.ui_hacks import add_compact_file_list_styles
    add_compact_file_list_styles()

    # Сначала рендерим сайдбар (глобальный контекст Streamlit)
    render_sidebar(session)

    # ========================================================================
    # ПРОВЕРКА ИНИЦИАЛИЗАЦИИ СЕРВИСОВ
    # ========================================================================
    redis_client = session.redis_client
    file_service = session.file_service

    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        st.caption("💡 Проверьте подключение к Redis и перезагрузите приложение")
        return

    if not file_service:
        st.error("❌ FileService не инициализирован")
        return

    # ========================================================================
    # ПОДПИСКА НА СОБЫТИЯ (один раз при первом запуске)
    # ========================================================================
    if not getattr(session, "_events_subscribed", False):
        try:
            session.subscribe_to_events()
            session._events_subscribed = True
            logger.info("✅ Подписка на события Redis активна")
        except AttributeError as e:
            logger.debug(f"⚠️ Пропуск подписки (сессия инициализируется): {e}")

    # ========================================================================
    # АВТООБНОВЛЕНИЕ СТРАНИЦЫ
    # ========================================================================
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
    log_col, stats_col = st.columns([3, 2], gap="medium")

    with log_col:
        logs = session.get_logs(limit=10)
        render_log_viewer(
            logs=logs,
            title="📋 Журнал событий",
            show_pending_warning=session.pending_events,
            on_clear=session.clear_logs,
            limit=10,
            compact_mode=True
        )

    with stats_col:
        stats = get_file_stats_cached(redis_client, _cache_key=session.cache_buster)
        render_stats_panel(stats, show_progress=True)

    st.divider()

    # ========================================================================
    # 📄 НИЖНЯЯ ЧАСТЬ: Реестр файлов
    # ========================================================================
    st.subheader("📄 Реестр файлов")

    # Панель управления списком
    control_col1, control_col2 = st.columns([4, 1])
    with control_col1:
        status_text = "🟢 Авто" if auto_refresh_enabled else "⏸️ Пауза"
        st.caption(f"🔄 {status_text} | {auto_refresh_interval_sec:.0f}с | Кэш: 30с")
    with control_col2:
        if st.button("🔄 Обновить", key="refresh_files_btn", use_container_width=True, type="primary"):
            session.invalidate_cache()
            st.rerun()

    # ========================================================================
    # CALLBACKS ДЛЯ ДЕЙСТВИЙ С ФАЙЛАМИ
    # ========================================================================

    def _on_edit(file_id: str) -> None:
        """Обработчик редактирования файла."""
        session.navigate("edit", file_id=file_id)
        st.rerun()

    def _on_export(file_id: str) -> None:
        """Обработчик экспорта в 1С."""
        try:
            from ui.utils.redis_helpers import push_job_to_queue, REDIS_QUEUES
            import json

            job_payload = json.dumps({
                "file_id": file_id,
                "action": "export_1c",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            if push_job_to_queue(session.redis_client, REDIS_QUEUES["export"], job_payload):
                session.add_log("OK", f"Запрос на экспорт в 1С: {file_id}")
                st.success("📤 Запрос на экспорт отправлен")
                session.invalidate_cache()
                st.rerun()
            else:
                st.error("❌ Не удалось отправить задачу на экспорт")

        except Exception as e:
            logger.error(f"Ошибка экспорта файла {file_id}: {e}", exc_info=True)
            st.error(f"❌ Ошибка экспорта: {e}")
            session.add_log("ERROR", f"Экспорт в 1С не удался: {file_id} — {e}")

    # ========================================================================
    # РЕНДЕРИНГ СПИСКА ФАЙЛОВ (публичный API компонента)
    # ========================================================================
    files = get_files_from_redis_cached(redis_client, _cache_key=session.cache_buster)

    render_file_list(
        files=files,
        session_state=session,
        mode="cards",  # Режим отображения: "cards" | "table"
        on_edit=_on_edit,
        on_export=_on_export
        # Остальные колбэки (on_detail, on_retry, on_delete) убраны — не используются в карточке
    )

    # Обновляем время последнего запроса (для расчёта uptime)
    session.update_refresh_time()


def render_sidebar(session: SessionState) -> None:
    """
    Рендерит боковую панель настроек.

    Содержит: автообновление, фильтры, статус системы.
    """
    with st.sidebar:
        st.header("⚙️ Настройки")

        # 🔹 Блок: Автообновление
        render_refresh_settings(session, key_prefix="main")
        st.divider()

        # 🔹 Блок: Фильтры
        st.subheader("🔍 Фильтры")
        status_filter = st.multiselect(
            "Статус",
            ["uploaded", "processing", "completed", "failed", "exported"],
            default=session.get_filter("status", [])
        )
        session.set_filter("status", status_filter)
        st.divider()

        # 🔹 Блок: Статус системы
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

        # 🔹 Футер сайдбара
        settings = session.settings if hasattr(session, "settings") and session.settings else get_settings()
        st.caption(f"📦 Algofusion v{settings.app_version}")
        st.caption(f"🌐 {settings.environment.upper()}")