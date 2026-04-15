# ui/components/file_list.py
"""
Компонент: Список файлов в реестре.
Использует существующие утилиты из ui.utils.*
"""

import streamlit as st
from typing import Any, List, Dict, Optional, Callable, Literal
from pathlib import Path

from shared.utils.logger import setup_logger
from shared.utils.helpers import get_safe_file_path
from ui.utils.constants import UI_CONFIG, FILE_STATUS_CONFIG, MODULES_ORDER
from ui.utils.formatters import (
    format_datetime_short,
    format_file_size,
    render_status_badge_safe,
    render_module_badge_safe,
    truncate_filename
)
from ui.utils.components import error_handler, render_columns_config, render_action_button, render_empty_state

logger = setup_logger("ui.components.file_list")

# Базовая директория для валидации
BASE_FILES_DIR = Path("/shared/files")


def render_file_list(
        files: List[Dict[str, Any]],
        session_state: Any,
        mode: Literal["table", "cards"] = "table",
        on_detail: Optional[Callable[[str], None]] = None,
        on_edit: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """Рендерит список файлов в выбранном режиме."""
    with error_handler("file_list", "Ошибка отображения списка файлов"):
        file_service = getattr(session_state, "file_service", None)

        if not files:
            render_empty_state("Файлы пока не загружены. Ожидание новых файлов...")
            return

        if mode == "table":
            _render_table_mode(files, session_state, on_detail)
        else:
            _render_cards_mode(
                files, file_service,
                on_edit, on_export
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
        file_service: Optional[Any],
        on_edit: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """Режим карточек с expanders."""
    st.caption(f"📄 Найдено файлов: {len(files)}")

    for idx, file in enumerate(files):
        _render_file_card(
            file, idx, file_service,
            on_edit, on_export
        )


def _render_file_card(
        file: Dict[str, Any],
        idx: int,
        file_service: Optional[Any],
        on_edit: Optional[Callable[[str], None]] = None,
        on_export: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Компактная карточка файла.
    🔹 Заголовок всегда виден.
    🔹 Детали и кнопки внутри раскрывающегося списка (Expander).
    """
    file_id = file.get("file_id", f"file_{idx}")
    filename = file.get("original_filename", "unknown")
    file_size = file.get("file_size", 0)
    status = file.get("status", "unknown")
    created_at = format_datetime_short(file.get("created_at"))
    size_formatted = format_file_size(file_size)
    current_module = file.get("current_module", "")

    # 🔹 Классификация из метаданных
    metadata = file.get("metadata", {})
    doc_type = metadata.get("document_type", "—")
    confidence = metadata.get("classification_confidence")
    conf_str = f"{confidence:.0%}" if confidence is not None else "—"
    classification_str = f"{doc_type} ({conf_str})" if doc_type not in ("unknown", "—") else "Не определено"

    # 🔹 Статус для отображения
    status_config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    status_label = status_config["label"]
    status_color = status_config["color"]
    status_bg = status_config["bg"]

    # ========================================================================
    # 🔹 1. ЗАГОЛОВОК: Всегда виден (Название + Статус)
    # ========================================================================
    header_left, header_right = st.columns([4, 1], gap="small")

    with header_left:
        # Крупное название файла
        st.markdown(f"### 📄 {truncate_filename(filename, 45)}")

    with header_right:
        # Бейдж статуса справа
        st.markdown(
            f"<span style='background:{status_bg};color:{status_color};padding:4px 10px;border-radius:10px;font-weight:700;font-size:0.9rem'>{status_label}</span>",
            unsafe_allow_html=True
        )

    # ========================================================================
    # 🔹 2. ЭКСПАНДЕР: Скрытые детали и действия (По умолчанию закрыт)
    # ========================================================================
    with st.expander("📊 Детали и действия", expanded=False, key=f"exp_{file_id}"):

        # --- Строка с информацией ---
        col_id, col_date, col_size, col_module, col_class = st.columns(5, gap="small")

        with col_id:
            st.markdown("**<span style='font-size:1.0rem'>ID</span>**", unsafe_allow_html=True)
            st.code(file_id[:10], language="text")

        with col_date:
            st.markdown("**<span style='font-size:1.0rem'>Загружен</span>**", unsafe_allow_html=True)
            st.write(created_at)

        with col_size:
            st.markdown("**<span style='font-size:1.0rem'>Размер</span>**", unsafe_allow_html=True)
            st.write(size_formatted)

        with col_module:
            st.markdown("**<span style='font-size:1.0rem'>Сейчас</span>**", unsafe_allow_html=True)
            st.write(current_module if current_module else "—")

        with col_class:
            st.markdown("**<span style='font-size:1.0rem'>Классификация</span>**", unsafe_allow_html=True)
            st.write(classification_str)

        st.divider()

        # --- Кнопки действий ---
        st.markdown("###### ⚙️ Действия")

        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")

        # 🔹 УНИКАЛЬНЫЕ КЛЮЧИ
        key_orig = f"dl_orig_{file_id}"
        key_prep = f"dl_prep_{file_id}"
        key_edit = f"edit_{file_id}"
        key_export = f"export_{file_id}"

        # Проверка существования файла
        file_path = get_safe_file_path(file_id, filename, BASE_FILES_DIR)
        file_exists = file_path is not None and file_path.exists() if file_path else False

        # Кнопка 1: Скачать оригинал
        with btn_col1:
            orig_disabled = not (file_service and file_exists)
            if not orig_disabled:
                original_path = file_service.get_download_path(file_id, "original")
                orig_disabled = not (original_path and original_path.exists())

            if orig_disabled:
                st.button("📥 Оригинал", key=key_orig, disabled=True, use_container_width=True)
            else:
                with open(original_path, "rb") as f:
                    st.download_button(
                        label="📥 Оригинал", data=f.read(), file_name=filename,
                        mime="application/octet-stream", key=key_orig,
                        use_container_width=True
                    )

        # Кнопка 2: Скачать результат предобработки
        with btn_col2:
            prep_disabled = not (file_service and file_exists)
            if not prep_disabled:
                prep_path = file_service.get_download_path(file_id, "preprocessed")
                prep_disabled = not (prep_path and prep_path.exists())

            if prep_disabled:
                st.button("📥 Результат", key=key_prep, disabled=True, use_container_width=True)
            else:
                with open(prep_path, "rb") as f:
                    st.download_button(
                        label="📥 Результат", data=f.read(),
                        file_name=f"{filename}_processed.png", mime="image/png",
                        key=key_prep, use_container_width=True
                    )

        # Кнопка 3: Редактировать
        with btn_col3:
            edit_clicked = st.button(
                "✏️ Править",
                key=key_edit,
                disabled=(on_edit is None),
                use_container_width=True
            )
            if edit_clicked and on_edit:
                on_edit(file_id)

        # Кнопка 4: Экспорт в 1С
        with btn_col4:
            export_disabled = status not in ("completed", "exported") or not file_exists
            export_clicked = st.button(
                "✅ Экспортировано" if status == "exported" else "📤 Экспорт",
                key=key_export,
                disabled=export_disabled or (on_export is None),
                use_container_width=True
            )
            if export_clicked and on_export and not export_disabled:
                on_export(file_id)


def _default_navigate_to_detail(file_id: str, session_state: Any) -> None:
    """Дефолтная навигация (если callback не передан)."""
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