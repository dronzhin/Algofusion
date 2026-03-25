"""
Страница деталей файла.
Использует централизованные утилиты из ui/utils/* для устранения дублирования.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================

import streamlit as st
import json  # ← ДОБАВЛЕНО: требуется для json.dumps
from typing import Dict, Any, Optional
from datetime import datetime, timezone  # ← ДОБАВЛЕНО: требуется для datetime.now(timezone.utc)

from shared.utils.logger import setup_logger
from shared.models.file import FileJob, FileStatus, ExportStatus
from ui.utils.constants import MODULES_ORDER, FILE_STATUS_CONFIG, EXPORT_STATUS_CONFIG, UI_CONFIG
from ui.utils.formatters import (
    format_datetime_full,
    format_file_size_human,
    render_status_badge,
    render_export_status_badge,
    calculate_module_progress,
)
from ui.utils.components import (
    error_handler,
    render_section_header,
    render_action_button,
    render_empty_state,
)
from ui.utils.redis_helpers import (
    safe_get_all_files,
    safe_update_file_status,
    push_job_to_queue,
    safe_get_file_status,
)

logger = setup_logger("ui.pages.file_detail_page")


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def render_file_detail_page(session_state) -> None:
    """
    Рендерит страницу деталей файла.

    Args:
        session_state: Экземпляр SessionState для навигации и данных
    """
    with error_handler("file_detail_page", "Ошибка загрузки деталей файла"):
        file_index = session_state.editing_file_index
        redis_client = session_state.redis_client
        file_service = session_state.file_service

        # Валидация входных данных
        if file_index is None or not redis_client:
            st.error("❌ Файл не выбран")
            _render_back_button(session_state)
            return

        files = safe_get_all_files(redis_client)
        if file_index is None or file_index >= len(files):
            st.error("❌ Файл не найден")
            _render_back_button(session_state)
            return

        file_data = files[file_index]
        file_id = file_data.get("file_id")

        logger.info(f"Рендеринг деталей файла: {file_id}")

        # Заголовок и навигация
        st.title("📋 Детали файла")
        _render_back_button(session_state)
        st.divider()

        # Основная информация (3 колонки)
        col1, col2, col3 = st.columns(3)

        with col1:
            _render_file_info_col(file_data)

        with col2:
            _render_status_col(file_data)  # ← ИСПРАВЛЕНО: file_data

        with col3:
            _render_export_col(file_data)  # ← ИСПРАВЛЕНО: file_data

        st.divider()

        # Прогресс по модулям
        render_section_header("📈 Прогресс обработки")
        _render_module_progress(file_data)

        st.divider()

        # История обработки
        render_section_header("📜 История обработки")
        _render_history(file_data)

        st.divider()

        # Файлы в структуре
        render_section_header("📂 Файлы в структуре")
        _render_file_structure(file_id, file_service)

        st.divider()

        # Действия
        render_section_header("⚡ Действия")
        _render_actions(file_id, file_data, redis_client)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def _render_back_button(session_state) -> None:
    """Кнопка возврата к реестру."""
    if st.button("← Вернуться к реестру", key="back_to_list"):
        session_state.current_page = "main"
        session_state.editing_file_index = None
        st.rerun()


def _render_file_info_col(file_data: Dict[str, Any]) -> None:
    """Рендерит колонку с основной информацией о файле."""
    st.markdown("### 📁 Основная информация")
    st.markdown(f"**ID:** `{file_data.get('file_id', 'unknown')}`")
    st.markdown(f"**Имя:** {file_data.get('original_filename', 'Unknown')}")
    st.markdown(f"**Тип:** `{file_data.get('file_type', 'unknown')}`")
    st.markdown(f"**Размер:** {format_file_size_human(file_data.get('file_size', 0))}")

    # Дополнительные метаданные если есть
    metadata = file_data.get('metadata', {})
    if metadata:
        with st.expander("📦 Метаданные", expanded=False):
            for key, value in metadata.items():
                st.markdown(f"**{key}:** {value}")


def _render_status_col(file_data: Dict[str, Any]) -> None:  # ← ИСПРАВЛЕНО: file_data: Dict
    """Рендерит колонку со статусом обработки."""
    st.markdown("### 📊 Статус обработки")

    status = file_data.get("status", "unknown")
    # ← FIX: unsafe_allow_html=True для рендеринга цветных бейджей
    st.markdown(f"**Статус:** {render_status_badge(status)}", unsafe_allow_html=True)

    current_module = file_data.get("current_module")
    module_display = f"`{current_module}`" if current_module else "—"
    st.markdown(f"**Модуль:** {module_display}")

    st.markdown(f"**Создан:** {format_datetime_full(file_data.get('created_at'))}")
    st.markdown(f"**Обновлён:** {format_datetime_full(file_data.get('updated_at'))}")

    retry_count = file_data.get("retry_count", 0)
    max_retries = file_data.get("max_retries", 3)
    if retry_count > 0:
        st.caption(f"🔄 Попытки: {retry_count}/{max_retries}")


def _render_export_col(file_data: Dict[str, Any]) -> None:  # ← ИСПРАВЛЕНО: file_data: Dict
    """Рендерит колонку со статусом экспорта в 1С."""
    st.markdown("### 📤 Экспорт в 1С")

    export_status = file_data.get("export_status", "pending")
    # ← FIX: unsafe_allow_html=True
    st.markdown(f"**Статус:** {render_export_status_badge(export_status)}", unsafe_allow_html=True)

    st.markdown(f"**Попыток:** {file_data.get('export_attempts', 0)}")

    export_error = file_data.get("export_error")
    if export_error:
        st.error(f"❌ {export_error}")

    exported_at = file_data.get("exported_at")
    if exported_at:
        st.caption(f"✅ Экспортирован: {format_datetime_full(exported_at)}")

    doc_id = file_data.get("document_1c_id")
    if doc_id:
        st.caption(f"🆔 Документ 1С: `{doc_id}`")


def _render_module_progress(file_data: Dict[str, Any]) -> None:
    """
    Рендерит прогресс по модулям обработки.
    Использует общую функцию calculate_module_progress из utils.
    """
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    progress, status_texts = calculate_module_progress(completed, current)

    st.progress(progress / 100)
    st.caption(" | ".join(status_texts))

    # Детали по каждому модулю
    with st.expander("🔍 Детали по модулям", expanded=False):
        for module in MODULES_ORDER:
            if module in completed:
                st.markdown(f"✅ **{module}** — завершён")
            elif current == module:
                st.markdown(f"🔄 **{module}** — выполняется")
            else:
                st.markdown(f"⏳ **{module}** — ожидает")


def _render_history(file_data: Dict[str, Any]) -> None:
    """Рендерит историю обработки файла."""
    history = file_data.get("history", [])

    if not history:
        render_empty_state("История пуста — обработка ещё не начиналась")
        return

    # Показываем последние записи с учётом лимита
    display_limit = UI_CONFIG["max_logs_display"]
    for record in reversed(history[-display_limit:]):
        _render_history_record(record)


def _render_history_record(record: Dict[str, Any]) -> None:
    """Рендерит одну запись истории."""
    timestamp = format_datetime_full(record.get("timestamp"))
    module = record.get("module", "unknown")
    action = record.get("action", "unknown")
    success = record.get("success", False)
    error = record.get("error")
    duration = record.get("duration_seconds")

    emoji = "✅" if success else "❌"
    duration_str = f" ({duration:.2f}с)" if duration else ""

    st.markdown(f"{emoji} **{timestamp}** — `{module}`: {action}{duration_str}")

    if error:
        st.caption(f"🔴 Ошибка: {error}")


def _render_file_structure(file_id: str, file_service) -> None:
    """Рендерит структуру файлов на диске."""
    if not file_service:
        render_empty_state("⚠️ FileService не доступен")
        return

    with error_handler("file_structure", "Ошибка получения структуры файлов"):
        file_info = file_service.get_file_info(file_id)

        if not file_info:
            render_empty_state("⚠️ Информация о файле не найдена на диске")
            return

        directories = file_info.get("directories", {})
        if not directories:
            render_empty_state("📭 Папки пустые")
            return

        for folder, info in directories.items():
            file_count = info.get("file_count", 0)
            with st.expander(f"📁 {folder} ({file_count} файлов)", expanded=False):
                st.caption(f"📍 `{info.get('path', '')}`")

                files = info.get("files", [])
                if files:
                    for filename in files[:20]:  # Лимит на отображение
                        st.markdown(f"📄 `{filename}`")
                    if len(files) > 20:
                        st.caption(f"... и ещё {len(files) - 20} файлов")
                else:
                    st.caption("📭 Пусто")


def _render_actions(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """Рендерит кнопки действий с файлом."""
    col1, col2, col3 = st.columns(3)

    with col1:
        _render_retry_button(file_id, file_data, redis_client)

    with col2:
        _render_export_button(file_id, file_data, redis_client)

    with col3:
        _render_delete_button(file_id, redis_client)


def _render_retry_button(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """Кнопка перезапуска обработки."""
    status = file_data.get("status", "")
    disabled = status in ["processing", "exporting"]

    if render_action_button(
            "🔄 Перезапустить",
            key=f"retry_{file_id}",
            disabled=disabled,
            help="Сбросить прогресс и начать обработку заново" if not disabled else "Файл уже обрабатывается"
    ):
        _handle_retry_action(file_id, file_data, redis_client)


def _handle_retry_action(
        file_id: str,
        file_data: Dict[str, Any],  # ← ИСПРАВЛЕНО: file_data: Dict[str, Any]
        redis_client: Any
) -> None:
    """Обработчик действия перезапуска."""
    try:
        # ← FIX: Получаем текущее время один раз
        retry_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        updates = {
            "status": FileStatus.PROCESSING.value,
            "current_module": "preprocess",
            "completed_modules": [],
            "retry_count": file_data.get("retry_count", 0) + 1,
            "errors": file_data.get("errors", []) + [f"Retry initiated at {retry_timestamp}"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        job_data = {**file_data, **updates}

        # ← FIX: Сериализуем и парсим через from_payload для конвертации строк в Enum
        payload = json.dumps(job_data, ensure_ascii=False)
        job = FileJob.from_payload(payload)

        if push_job_to_queue(redis_client, "preprocess", job.to_payload(), priority=10):
            st.success("✅ Обработка перезапущена с высоким приоритетом")
            st.rerun()
        else:
            st.error("❌ Не удалось отправить задачу в очередь")

    except Exception as e:
        logger.error(f"Ошибка при перезапуске обработки {file_id}: {e}", exc_info=True)
        st.error(f"❌ Ошибка: {e}")


def _render_export_button(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """Кнопка экспорта в 1С."""
    export_status = file_data.get("export_status", "")
    file_status = file_data.get("status", "")

    # Блокируем если: уже экспортирован, в процессе экспорта, или файл не завершён
    disabled = (
            export_status == ExportStatus.SUCCESS.value or
            export_status == ExportStatus.EXPORTING.value or
            file_status != FileStatus.COMPLETED.value
    )

    help_text = "Отправить файл на экспорт в 1С"
    if export_status == ExportStatus.SUCCESS.value:
        help_text = "✅ Уже экспортирован"
    elif file_status != FileStatus.COMPLETED.value:
        help_text = "⏳ Сначала завершите обработку файла"

    if render_action_button(
            "📤 Экспорт в 1С",
            key=f"export_{file_id}",
            disabled=disabled,
            help=help_text
    ):
        _handle_export_action(file_id, file_data, redis_client)


def _handle_export_action(
        file_id: str,
        file_data: Dict[str, Any],  # ← ИСПРАВЛЕНО: file_data: Dict[str, Any]
        redis_client: Any
) -> None:
    """Обработчик действия экспорта."""
    try:
        updates = {
            "export_status": ExportStatus.EXPORTING.value,
            "export_attempts": file_data.get("export_attempts", 0) + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if not safe_update_file_status(redis_client, file_id, updates):
            st.error("❌ Не удалось обновить статус экспорта")
            return

        # ← FIX: Создаём Job через from_payload
        job_data = {**file_data, **updates}
        payload = json.dumps(job_data, ensure_ascii=False)  # ← FIX: было ensure_allow_ascii
        job = FileJob.from_payload(payload)

        if push_job_to_queue(redis_client, "export", job.to_payload(), priority=5):
            st.success("✅ Экспорт запущен")
            st.rerun()
        else:
            st.error("❌ Не удалось отправить задачу экспорта в очередь")

    except Exception as e:
        logger.error(f"Ошибка при запуске экспорта {file_id}: {e}", exc_info=True)
        st.error(f"❌ Ошибка: {e}")


def _render_delete_button(file_id: str, redis_client) -> None:
    """Кнопка удаления файла с подтверждением."""
    if render_action_button(
            "🗑️ Удалить",
            key=f"delete_{file_id}",
            type="secondary",
            help="⚠️ Безвозвратно удалить файл и все артефакты"
    ):
        # Показываем модальное подтверждение
        st.warning("⚠️ Подтвердите удаление")
        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("✅ Да, удалить", key=f"confirm_delete_{file_id}", type="primary"):
                _handle_delete_action(file_id, redis_client)

        with col_no:
            if st.button("❌ Отмена", key=f"cancel_delete_{file_id}"):
                st.rerun()


def _handle_delete_action(file_id: str, redis_client) -> None:
    """Обработчик действия удаления."""
    try:
        # Удаляем статус из Redis
        if redis_client.delete_file_status(file_id):
            st.success("✅ Файл удалён из реестра")
            # Возвращаем к списку
            st.session_state.current_page = "main"
            st.session_state.editing_file_index = None
            st.rerun()
        else:
            st.error("❌ Не удалось удалить файл")

    except Exception as e:
        logger.error(f"Ошибка при удалении файла {file_id}: {e}", exc_info=True)
        st.error(f"❌ Ошибка: {e}")