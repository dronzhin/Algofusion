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
    # 🔹 НОВЫЕ ПАРАМЕТРЫ:
    on_download_preprocessed: Optional[Callable[[str], None]] = None,
    on_edit: Optional[Callable[[str], None]] = None,
    on_export: Optional[Callable[[str], None]] = None,
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
            # 🔹 Прокидываем новые колбэки в режим карточек
            _render_cards_mode(
                files,
                session_state,
                file_service,
                on_detail,
                on_retry,
                on_delete,
                on_download_preprocessed,  # ← новый
                on_edit,                   # ← новый
                on_export                  # ← новый
            )

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
    file_service: Optional[Any],
    on_detail: Optional[Callable[[str], None]],
    on_retry: Optional[Callable[[str], None]],
    on_delete: Optional[Callable[[str], None]],
    # 🔹 НОВЫЕ ПАРАМЕТРЫ:
    on_download_preprocessed: Optional[Callable[[str], None]] = None,
    on_edit: Optional[Callable[[str], None]] = None,
    on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """Режим карточек с expanders."""
    from ui.components.file_preview import render_file_preview

    st.caption(f"📄 Найдено файлов: {len(files)}")

    for idx, file in enumerate(files):
        _render_file_card(
            file,
            idx,
            session_state,
            file_service,
            on_detail,
            on_retry,
            on_delete,
            on_download_preprocessed,  # ← новый
            on_edit,                   # ← новый
            on_export                  # ← новый
        )


def _render_file_card(
        file: Dict[str, Any],
        idx: int,
        session_state: Any,
        file_service: Optional[Any],
        on_detail: Optional[Callable[[str], None]] = None,
        on_retry: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        on_download_preprocessed: Optional[Callable[[str], None]] = None,
        on_edit: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Компактная карточка файла.

    Header: 📁 filename (слева) + статус (справа)
    Content: ID, время, размер + 4 основные кнопки
    """
    file_id = file.get("file_id", f"file_{idx}")
    filename = file.get("original_filename", "unknown")
    file_size = file.get("file_size", 0)
    status = file.get("status", "unknown")
    created_at = format_datetime_short(file.get("created_at"))
    size_formatted = format_file_size(file_size)

    # 🔹 Иконка статуса для заголовка
    status_icon = {
        "uploaded": "📁", "processing": "⏳", "completed": "✅",
        "exported": "📤", "failed": "❌"
    }.get(status, "❓")

    # 🔹 Цвет бейджа статуса
    status_config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    status_label = status_config["label"]
    status_color = status_config["color"]
    status_bg = status_config["bg"]

    # 🔹 Заголовок: название слева, статус справа
    header_left, header_right = st.columns([4, 1], gap="small")

    with header_left:
        truncated_name = truncate_filename(filename, 50)
        st.markdown(f"**{status_icon} {truncated_name}**")

    with header_right:
        badge_html = f"""
        <span style="
            background-color: {status_bg};
            color: {status_color};
            padding: 3px 8px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 10px;
            white-space: nowrap;
        ">
            {status_label}
        </span>
        """
        st.markdown(badge_html, unsafe_allow_html=True)

    # 🔹 Expander с контентом (только основное)
    with st.expander("📊 Детали", expanded=False):
        # Информация о файле
        info_col1, info_col2, info_col3 = st.columns(3, gap="small")
        with info_col1:
            st.caption("🆔 ID")
            st.code(file_id[:12], language="text")
        with info_col2:
            st.caption("📅 Загружен")
            st.write(f"`{created_at}`")
        with info_col3:
            st.caption("📦 Размер")
            st.write(f"`{size_formatted}`")

        # 🔹 4 основные кнопки с текстовыми labels
        st.markdown("##### ⚙️ Действия")

        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")

        # Кнопка 1: Скачать оригинал
        with btn_col1:
            if file_service:
                original_path = file_service.get_download_path(file_id, "original")
                if original_path and original_path.exists():
                    with open(original_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать оригинал",  # ← Текст + иконка
                            data=f.read(),
                            file_name=filename,
                            mime="application/octet-stream",
                            key=f"dl_orig_{idx}",
                            use_container_width=True,
                            help="Скачать исходный файл"
                        )
                else:
                    st.button("📥 Скачать оригинал", key=f"dl_orig_{idx}", disabled=True, use_container_width=True)
            else:
                st.button("📥 Скачать оригинал", key=f"dl_orig_{idx}", disabled=True, use_container_width=True)

        # Кнопка 2: Скачать предобработанный
        with btn_col2:
            if file_service:
                preprocessed_path = file_service.get_download_path(file_id, "preprocessed")
                if preprocessed_path and preprocessed_path.exists():
                    with open(preprocessed_path, "rb") as f:
                        st.download_button(
                            label="📥 Скачать обр.",  # ← Короткий текст
                            data=f.read(),
                            file_name=f"preprocessed_{filename}",
                            mime="application/octet-stream",
                            key=f"dl_prep_{idx}",
                            use_container_width=True,
                            help="Скачать файл после обработки"
                        )
                else:
                    st.button("📥 Скачать обр.", key=f"dl_prep_{idx}", disabled=True, use_container_width=True,
                              help="Файл не готов")
            else:
                st.button("📥 Скачать обр.", key=f"dl_prep_{idx}", disabled=True, use_container_width=True)

        # Кнопка 3: Редактировать
        with btn_col3:
            if on_edit:
                if st.button("✏️ Редактировать", key=f"edit_{idx}", use_container_width=True,
                             help="Редактировать файл"):
                    on_edit(file_id)
            else:
                st.button("✏️ Редактировать", key=f"edit_{idx}", disabled=True, use_container_width=True)

        # Кнопка 4: Экспорт в 1С
        with btn_col4:
            if on_export:
                export_status = file.get("export_status", "none")
                export_disabled = (export_status in ("exporting", "success")) or (
                            status not in ("completed", "exported"))

                export_label = "📤 Экспорт в 1С"
                if export_status == "success":
                    export_label = "✅ Экспортировано"
                elif export_status == "exporting":
                    export_label = "🔄 В процессе"

                if st.button(
                        export_label,
                        key=f"export_{idx}",
                        use_container_width=True,
                        disabled=export_disabled,
                        help="Экспортировать в 1С" if not export_disabled else f"Статус: {export_status}"
                ):
                    on_export(file_id)
            else:
                st.button("📤 Экспорт в 1С", key=f"export_{idx}", disabled=True, use_container_width=True)

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