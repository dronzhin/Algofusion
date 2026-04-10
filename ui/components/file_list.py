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
    """Компактная карточка файла с отображением прогресса по всем модулям."""
    file_id = file.get("file_id", f"file_{idx}")
    filename = file.get("original_filename", "unknown")
    file_size = file.get("file_size", 0)
    status = file.get("status", "unknown")
    created_at = format_datetime_short(file.get("created_at"))
    size_formatted = format_file_size(file_size)

    # Иконка статуса для заголовка
    status_icon = {
        "uploaded": "📁", "processing": "⏳", "completed": "✅",
        "exported": "📤", "failed": "❌"
    }.get(status, "❓")

    # Цвет бейджа статуса
    status_config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    status_label = status_config["label"]
    status_color = status_config["color"]
    status_bg = status_config["bg"]

    # Заголовок: название слева, статус справа
    header_left, header_right = st.columns([4, 1], gap="small")

    with header_left:
        truncated_name = truncate_filename(filename, 40)
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

    # 🔹 Проверяем существование файла на диске
    file_path = get_safe_file_path(file_id, filename, BASE_FILES_DIR)
    file_exists = file_path is not None and file_path.exists()

    # 🔹 Expander с контентом
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

        # Прогресс по модулям
        st.markdown("##### 🔄 Прогресс обработки")

        completed_modules = set(file.get("completed_modules", []))
        current_module = file.get("current_module", "")

        def get_module_status(module_name: str) -> str:
            if status == "failed":
                return "failed"
            if module_name in completed_modules:
                return "completed"
            if module_name == current_module:
                return "processing"
            return "pending"

        module_cols = st.columns(len(MODULES_ORDER), gap="small")
        for i, module_name in enumerate(MODULES_ORDER):
            mod_status = get_module_status(module_name)
            with module_cols[i]:
                render_module_badge_safe(
                    module=module_name, status=mod_status,
                    container=module_cols[i], size="small", show_tooltip=True
                )

        if status == "processing" and current_module:
            st.caption(f"⏳ Сейчас: {current_module}")
        elif status == "completed":
            st.caption("✅ Все этапы завершены")
        elif status == "failed":
            st.caption("❌ Ошибка обработки — файл будет обработан повторно")

        st.divider()

        st.markdown("##### 📋 Классификация")
        from ui.components.classification_badge import render_classification_info
        render_classification_info(file, container=st)

        st.divider()

        st.markdown("##### ⚙️ Действия")

        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")

        # Кнопка 1: Скачать оригинал
        with btn_col1:
            if file_service and file_exists:
                original_path = file_service.get_download_path(file_id, "original")
                if original_path and original_path.exists():
                    with open(original_path, "rb") as f:
                        st.download_button(
                            label="📥 Оригинал", data=f.read(), file_name=filename,
                            mime="application/octet-stream", key=f"dl_orig_{idx}",
                            use_container_width=True, help="Скачать исходный файл"
                        )
                else:
                    st.button("📥 Оригинал", key=f"dl_orig_{idx}", disabled=True, use_container_width=True)
            else:
                disabled_help = "Файл не найден на диске" if not file_exists else "FileService не доступен"
                st.button("📥 Оригинал", key=f"dl_orig_{idx}", disabled=True, use_container_width=True, help=disabled_help)

        # Кнопка 2: Скачать результат предобработки
        with btn_col2:
            preprocess_status = get_module_status("preprocess")
            if preprocess_status == "completed" and file_service and file_exists:
                preprocessed_path = file_service.get_download_path(file_id, "preprocessed")
                if preprocessed_path and preprocessed_path.exists():
                    with open(preprocessed_path, "rb") as f:
                        st.download_button(
                            label="📥 Результат", data=f.read(),
                            file_name=f"{filename}_processed.png", mime="image/png",
                            key=f"dl_prep_{idx}", use_container_width=True,
                            help="Скачать обработанный файл"
                        )
                else:
                    st.button("📥 Результат", key=f"dl_prep_{idx}", disabled=True, use_container_width=True)
            else:
                btn_help = {
                    "pending": "Ожидает обработки",
                    "processing": "Обработка в процессе...",
                    "failed": "Ошибка обработки",
                }.get(preprocess_status, "Недоступно")
                if not file_exists:
                    btn_help = "Файл не найден на диске"
                st.button("📥 Результат", key=f"dl_prep_{idx}", disabled=True, use_container_width=True, help=btn_help)

        # Кнопка 3: Редактировать
        with btn_col3:
            if on_edit:
                if st.button("✏️ Править", key=f"edit_{idx}", use_container_width=True, help="Редактировать файл"):
                    on_edit(file_id)
            else:
                st.button("✏️ Править", key=f"edit_{idx}", disabled=True, use_container_width=True)

        # Кнопка 4: Экспорт в 1С
        with btn_col4:
            if on_export:
                all_completed = all(get_module_status(m) == "completed" for m in ["preprocess", "ocr", "llm"])
                export_disabled = not all_completed or status not in ("completed", "exported") or not file_exists

                export_label = "📤 Экспорт"
                if status == "exported":
                    export_label = "✅ Экспортировано"

                export_help = "Экспортировать в 1С"
                if not file_exists:
                    export_help = "Файл не найден на диске"
                elif not all_completed:
                    export_help = "Завершите все этапы обработки"

                if st.button(export_label, key=f"export_{idx}", use_container_width=True,
                            disabled=export_disabled, help=export_help):
                    on_export(file_id)
            else:
                st.button("📤 Экспорт", key=f"export_{idx}", disabled=True, use_container_width=True)

        # 🔹 Предупреждение, если файл не найден на диске (но показываем в списке как активный)
        if not file_exists and status in ("uploaded", "processing"):
            st.warning(
                f"⚠️ Файл `{filename}` временно недоступен на диске.\n"
                f"Возможно, он обрабатывается другим процессом."
            )
        elif not file_exists and status not in ("uploaded", "processing"):
            st.error(
                f"❌ Файл `{filename}` не найден на диске.\n"
                f"Возможные причины: файл удалён вручную, ошибка монтирования томов."
            )
            with st.expander("🔧 Технические детали", expanded=False):
                st.json({
                    "file_id": file_id,
                    "status": status,
                    "expected_path": str(get_safe_file_path(file_id, filename, BASE_FILES_DIR)),
                    "metadata": file.get("metadata", {})
                })


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