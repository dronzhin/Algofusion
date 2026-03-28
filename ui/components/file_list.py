# ui/components/file_list.py
"""
Компонент: Список файлов в реестре.
Использует существующие утилиты из ui.utils.*
"""

import streamlit as st
from typing import Any, List, Dict, Optional, Callable, Literal

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG, FILE_STATUS_CONFIG
from ui.utils.formatters import (
    format_datetime_short,
    format_file_size,
    render_status_badge_safe,
    truncate_filename
)
from ui.utils.components import error_handler, render_columns_config, render_action_button, render_empty_state

logger = setup_logger("ui.components.file_list")


def render_file_list(
        files: List[Dict[str, Any]],
        session_state: Any,
        mode: Literal["table", "cards"] = "table",
        on_detail: Optional[Callable[[str], None]] = None,
        on_retry: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
) -> None:
    """Рендерит список файлов в выбранном режиме."""
    with error_handler("file_list", "Ошибка отображения списка файлов"):
        # 🔹 Получаем file_service из session (единый источник)
        file_service = getattr(session_state, "file_service", None)

        if not files:
            render_empty_state("Файлы пока не загружены. Ожидание новых файлов...")
            return

        if mode == "table":
            _render_table_mode(files, session_state, on_detail)
        else:
            _render_cards_mode(files, session_state, file_service, on_detail, on_retry, on_delete)


def _render_table_mode(
    files: List[Dict[str, Any]],
    session_state: Any,
    on_detail: Optional[Callable[[str], None]]
) -> None:
    """Компактный табличный режим."""
    cols = render_columns_config([2, 3, 2, 2, 2, 1])
    headers = ["ID", "Файл", "Статус", "Модуль", "Время", "Действия"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.divider()

    display_files = files[-UI_CONFIG["max_files_display"]:]
    for file_data in reversed(display_files):
        _render_table_row(file_data, session_state, on_detail)
        st.divider()


def _render_table_row(
    file_data: Dict[str, Any],
    session_state: Any,
    on_detail: Optional[Callable[[str], None]]
) -> None:
    """Одна строка в табличном режиме."""
    file_id = file_data.get("file_id", "unknown")
    filename = file_data.get("original_filename", "Unknown")
    status = file_data.get("status", "unknown")
    current_module = file_data.get("current_module", "-")
    created_at = format_datetime_short(file_data.get("created_at"))

    cols = render_columns_config([2, 3, 2, 2, 2, 1])
    cols[0].code(file_id[:12], language="text")
    cols[1].markdown(f"📄 {truncate_filename(filename)}")
    render_status_badge_safe(status, cols[2])
    cols[3].markdown(f"`{current_module}`" if current_module else "-")
    cols[4].markdown(created_at)

    if render_action_button("📋", key=f"detail_{file_id}", help="Детали файла"):
        if on_detail:
            on_detail(file_id)
        else:
            _default_navigate_to_detail(file_id, session_state)


def _render_cards_mode(
        files: List[Dict[str, Any]],
        session_state: Any,
        file_service: Optional[Any],  # ← оставляем для внутренней передачи
        on_detail: Optional[Callable[[str], None]],
        on_retry: Optional[Callable[[str], None]],
        on_delete: Optional[Callable[[str], None]],
) -> None:
    """Режим карточек с expanders."""
    from ui.components.file_preview import render_file_preview

    st.caption(f"📄 Найдено файлов: {len(files)}")

    for idx, file in enumerate(files):
        _render_file_card(file, idx, session_state, file_service, on_detail, on_retry, on_delete)


def _render_file_card(
        file: Dict[str, Any],
        idx: int,
        session_state: Any,
        file_service: Optional[Any],  # ← используется внутри
        on_detail: Optional[Callable[[str], None]],
        on_retry: Optional[Callable[[str], None]],
        on_delete: Optional[Callable[[str], None]],
) -> None:
    """Карточка файла в режиме expanders."""
    from ui.components.file_preview import render_file_preview

    file_id = file.get("file_id", f"file_{idx}")
    filename = file.get("original_filename", "unknown")
    file_size = file.get("file_size", 0)
    status = file.get("status", "unknown")
    created_at = format_datetime_short(file.get("created_at"))
    size_formatted = format_file_size(file_size)

    status_icon = {
        "uploaded": "📁", "processing": "⏳", "completed": "✅",
        "exported": "📤", "failed": "❌"
    }.get(status, "❓")

    status_color = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])["color"]

    with st.expander(f"{status_icon} {truncate_filename(filename, 60)}", expanded=False):
        # Шапка
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**📄 Файл:** `{filename}`")
            st.caption(f"🆔 ID: `{file_id}`")
        with col2:
            st.caption(f"📅 Загружен: {created_at}")
            st.caption(f"📦 Размер: {size_formatted}")
        with col3:
            render_status_badge_safe(status, col3)

        st.divider()

        # Кнопки действий
        st.markdown("#### ⚙️ Действия")
        col_act1, col_act2, col_act3, col_act4, col_act5 = st.columns(5)

        with col_act1:
            if file_service:
                download_path = file_service.get_download_path(file_id, "original")
                if download_path and download_path.exists():
                    with open(download_path, "rb") as f:
                        st.download_button(
                            label="📥", key=f"dl_{idx}", data=f.read(),
                            file_name=filename, mime="application/octet-stream",
                            help="Скачать оригинал"
                        )
                else:
                    st.button("📥", key=f"dl_{idx}", disabled=True, help="Файл недоступен")
            else:
                st.button("📥", key=f"dl_{idx}", disabled=True)

        with col_act2:
            if st.button("👁️", key=f"view_{idx}", help="Предпросмотр"):
                render_file_preview(file_service, file_id, filename)

        with col_act3:
            if st.button("📋", key=f"meta_{idx}", help="Метаданные"):
                if file_service:
                    metadata = file_service.get_file_metadata(file_id)
                    if metadata:
                        with st.expander("📊 Метаданные", expanded=True):
                            for key, value in metadata.items():
                                st.caption(f"**{key}**: {value}")
                else:
                    st.warning("❌ Сервис файлов не доступен")

        with col_act4:
            if status == "failed" and on_retry:
                if st.button("🔄", key=f"retry_{idx}", help="Повторить"):
                    on_retry(file_id)
            else:
                st.button("🔄", key=f"retry_{idx}", disabled=True)

        with col_act5:
            if on_delete:
                if st.button("🗑️", key=f"del_{idx}", help="Удалить"):
                    with st.popover("⚠️ Подтвердите"):
                        st.warning(f"Удалить **{filename}**?")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Да", key=f"del_yes_{idx}"):
                                on_delete(file_id)
                        with c2:
                            if st.button("❌ Нет", key=f"del_no_{idx}"):
                                pass
            else:
                st.button("🗑️", key=f"del_{idx}", disabled=True)

        if st.button("🔍 Подробнее →", key=f"detail_{idx}", use_container_width=True):
            if on_detail:
                on_detail(file_id)
            else:
                _default_navigate_to_detail(file_id, session_state)


def _default_navigate_to_detail(file_id: str, session_state: Any) -> None:
    """Дефолтная навигация (если callback не передан)."""
    # 🔹 Используем redis_client из session_state
    redis_client = getattr(session_state, "redis_client", None)

    if redis_client:
        try:
            from ui.utils.redis_helpers import safe_get_all_files
            files = safe_get_all_files(redis_client)
            index = [f.get("file_id") for f in files].index(file_id)
            session_state.editing_file_index = index
            session_state.current_page = "detail"
            st.rerun()
        except (ValueError, AttributeError) as e:
            logger.warning(f"Не удалось найти файл {file_id}: {e}")
            st.error("❌ Файл не найден")