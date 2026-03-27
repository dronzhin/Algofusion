# ui/pages/main_page.py
"""
Главная страница мониторинга файлов.
Полное обновление страницы каждые 5 секунд.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from shared.utils.logger import setup_logger
from shared.utils.helpers import format_file_size, format_datetime
from ui.state import SessionState
from ui.cache import get_files_from_redis_cached, get_file_stats_cached, CacheManager

logger = setup_logger("ui.pages.main_page")


# ============================================================================
# КОМПОНЕНТЫ: СТАТИСТИКА
# ============================================================================

def _render_stats_panel(stats: dict) -> None:
    """Рендерит панель статистики."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("📁 Всего", stats.get("total", 0))
    with col2:
        st.metric("✅ Завершено", stats.get("completed", 0))
    with col3:
        st.metric("⏳ В обработке", stats.get("processing", 0))
    with col4:
        st.metric("❌ Ошибки", stats.get("failed", 0))
    with col5:
        st.metric("📤 Экспорт", stats.get("exported", 0))

    success_rate = stats.get("success_rate", "0%")
    try:
        rate_value = float(success_rate.replace("%", ""))
        st.progress(rate_value / 100)
        st.caption(f"✨ Успешность обработки: {success_rate}")
    except:
        st.caption(f"✨ Успешность обработки: {success_rate}")


# ============================================================================
# КОМПОНЕНТЫ: ЛОГИ
# ============================================================================

def _render_logs_panel(logs: list, pending: bool) -> None:
    """Рендерит панель логов."""
    st.markdown("### 📋 Журнал событий")

    if pending:
        st.warning("🔔 Есть новые события!", icon="🔔")

    if logs:
        logs_html = ""
        for log in logs[-20:]:
            icon = "✅" if log["status"] == "ОК" else "❌"
            color = "#28a745" if log["status"] == "ОК" else "#dc3545"
            logs_html += f"""
            <div style="
                padding: 6px 10px;
                margin: 3px 0;
                border-left: 4px solid {color};
                background: #f8f9fa;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border-radius: 3px;
            ">
                <span style="color: #666; font-weight: bold;">{log['time']}</span>
                <span style="color: {color}; font-weight: bold; margin: 0 8px;">{icon} {log['status']}</span>
                <span style="color: #333;">{log['msg']}</span>
            </div>
            """
        st.markdown(logs_html, unsafe_allow_html=True)
    else:
        st.info("📭 Пока нет событий в журнале")

    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption(f"Всего записей: {len(logs)}")
    with col2:
        if st.button("🧹 Очистить", key="clear_logs_btn", use_container_width=True):
            from ui.state import get_session_state
            session = get_session_state()
            session.clear_logs()
            st.rerun()


# ============================================================================
# КОМПОНЕНТЫ: ПРЕВЬЮ ФАЙЛА
# ============================================================================

def _show_file_preview(file_service, file_id: str, filename: str) -> None:
    """Показывает превью файла в экспандере."""
    text_preview = file_service.get_text_preview(file_id, "ocr")
    if text_preview:
        with st.expander(f"📄 Превью: {filename}", expanded=True):
            st.code(text_preview, language="text")
        return

    metadata = file_service.get_file_metadata(file_id)

    if metadata and metadata.get("is_image"):
        content = file_service.get_file_content(file_id)
        if content:
            with st.expander(f"🖼️ Изображение: {filename}", expanded=True):
                st.image(content, caption=filename)
        return

    if metadata and metadata.get("is_pdf"):
        with st.expander(f"📕 PDF: {filename}", expanded=True):
            st.info("📄 PDF-файлы можно скачать, но предпросмотр ограничен.")
            st.caption(f"Размер: {metadata.get('size_human')}")
        return

    st.info("📭 Предпросмотр недоступен для этого типа файла. Используйте кнопку «Скачать».")


# ============================================================================
# КОМПОНЕНТЫ: СПИСОК ФАЙЛОВ
# ============================================================================

def _render_file_list(files: list, session: SessionState, file_service) -> None:
    """Рендерит список файлов с действиями."""
    if not files:
        st.info("📭 Файлов не найдено")
        return

    st.caption(f"📄 Найдено файлов: {len(files)}")

    for idx, file in enumerate(files):
        file_id = file.get("file_id", f"file_{idx}")
        filename = file.get("original_filename", "unknown")
        file_size = file.get("file_size", 0)
        status = file.get("status", "unknown")
        created_at_raw = file.get("created_at", "—")

        # ✅ Используем общие хелперы из shared.utils.helpers
        created_at = format_datetime(created_at_raw)
        size_formatted = format_file_size(file_size)

        status_icon = {
            "uploaded": "📁", "processing": "⏳", "completed": "✅",
            "exported": "📤", "failed": "❌"
        }.get(status, "❓")

        status_color = {
            "uploaded": "#17a2b8", "processing": "#ffc107", "completed": "#28a745",
            "exported": "#6610f2", "failed": "#dc3545"
        }.get(status, "#6c757d")

        with st.expander(f"{status_icon} {filename}", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"**📄 Файл:** `{filename}`")
                st.caption(f"🆔 ID: `{file_id}`")

            with col2:
                st.caption(f"📅 Загружен: {created_at}")
                st.caption(f"📦 Размер: {size_formatted}")

            with col3:
                st.markdown(
                    f"""
                    <div style="
                        display: inline-block;
                        padding: 4px 12px;
                        background: {status_color};
                        color: white;
                        border-radius: 12px;
                        font-size: 12px;
                        font-weight: bold;
                    ">
                        {status_icon} {status.upper()}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.divider()
            st.markdown("#### ⚙️ Действия")
            col_act1, col_act2, col_act3, col_act4, col_act5 = st.columns(5)

            with col_act1:
                download_path = file_service.get_download_path(file_id, "original")
                if download_path and download_path.exists():
                    with open(download_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать",
                            data=f.read(),
                            file_name=filename,
                            mime="application/octet-stream",
                            key=f"dl_{idx}",
                            use_container_width=True
                        )
                else:
                    st.button("📥 Скачать", key=f"dl_{idx}", disabled=True, use_container_width=True)

            with col_act2:
                if st.button("👁️ Просмотр", key=f"view_{idx}", use_container_width=True):
                    _show_file_preview(file_service, file_id, filename)

            with col_act3:
                if st.button("📋 Инфо", key=f"meta_{idx}", use_container_width=True):
                    metadata = file_service.get_file_metadata(file_id)
                    if metadata:
                        with st.expander("📊 Метаданные", expanded=True):
                            for key, value in metadata.items():
                                st.caption(f"**{key}**: {value}")
                    else:
                        st.warning("❌ Не удалось получить метаданные")

            with col_act4:
                if status == "failed":
                    if st.button("🔄 Повторить", key=f"retry_{idx}", use_container_width=True, type="secondary"):
                        if file_service.retry_processing(file_id):
                            session.invalidate_cache()
                            st.success("✅ Запущена повторная обработка")
                            st.rerun()
                else:
                    st.button("🔄 Повторить", key=f"retry_{idx}", disabled=True, use_container_width=True)

            with col_act5:
                if st.button("🗑️ Удалить", key=f"del_{idx}", use_container_width=True, type="secondary"):
                    with st.popover("⚠️ Подтвердите удаление"):
                        st.warning(f"Удалить файл **{filename}**?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Да", key=f"del_yes_{idx}", use_container_width=True):
                                if file_service.delete_file(file_id):
                                    session.invalidate_cache()
                                    st.success("✅ Файл удалён")
                                    st.rerun()
                        with col_no:
                            if st.button("❌ Нет", key=f"del_no_{idx}", use_container_width=True):
                                pass

            if st.button("🔍 Подробнее →", key=f"detail_{idx}", use_container_width=True):
                session.navigate("detail", file_id=file_id)
                st.rerun()


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def render_main_page(session: SessionState) -> None:
    """Рендерит главную страницу мониторинга."""
    logger.info("📄 Рендеринг главной страницы")

    redis_client = session.redis_client
    if not redis_client:
        st.error("❌ Redis клиент не инициализирован")
        return

    # 🔁 АВТООБНОВЛЕНИЕ ВСЕЙ СТРАНИЦЫ (5 секунд)
    st_autorefresh(
        interval=5000,
        limit=None,
        key="main_page_auto_refresh",
        debounce=True
    )

    # 📊 ЗОНА 1: СТАТИСТИКА
    st.subheader("📈 Статистика обработки")
    stats = get_file_stats_cached(redis_client, _cache_key=session.cache_buster)
    _render_stats_panel(stats)

    st.divider()

    # 📋 ЗОНА 2: ЛОГИ
    logs = session.get_logs(limit=20)
    _render_logs_panel(logs, session.pending_events)

    st.divider()

    # 📁 ЗОНА 3: РЕЕСТР ФАЙЛОВ
    st.subheader("📄 Реестр файлов")

    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption(f"🔄 Автообновление: каждые 5 сек | Кэш: 30 сек")
    with col2:
        if st.button("🔄 Обновить сейчас", key="refresh_files_btn", use_container_width=True, type="primary"):
            session.invalidate_cache()
            st.rerun()

    # Загрузка файлов (ВСЕГДА)
    files = get_files_from_redis_cached(redis_client, _cache_key=session.cache_buster)
    _render_file_list(files, session, session.file_service)

    session.update_refresh_time()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def _render_sidebar(session: SessionState, redis_client) -> None:
    """Рендерит боковую панель настроек."""
    with st.sidebar:
        st.header("⚙️ Настройки")

        st.subheader("🔍 Фильтры")
        status_filter = st.multiselect(
            "Статус",
            ["uploaded", "processing", "completed", "failed", "exported"],
            default=session.get_filter("status", [])
        )
        session.set_filter("status", status_filter)

        st.divider()

        st.subheader("📡 Статус")
        try:
            redis_client.client.ping()
            st.success("✅ Redis подключен")
        except Exception:
            st.error("❌ Redis отключен")

        st.divider()
        st.caption(f"📦 Algofusion File Processor v0.1.0")
        st.caption(f"🔄 Автообновление: каждые 5 сек")