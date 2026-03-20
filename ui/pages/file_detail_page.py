# ui/pages/file_detail_page.py
"""
Страница деталей файла.
"""

import streamlit as st
from pathlib import Path
from typing import Dict, Any, Optional
from shared.utils.logger import setup_logger
from shared.models.file import FileJob, FileStatus, ExportStatus
from shared.utils.helpers import format_file_size, format_datetime

logger = setup_logger("ui.pages.file_detail_page")


def render_file_detail_page() -> None:
    """Рендерит страницу деталей файла."""
    file_index = st.session_state.get("editing_file_index")
    redis_client = st.session_state.get("redis_client")

    if file_index is None or not redis_client:
        st.error("❌ Файл не выбран")
        if st.button("← Вернуться назад"):
            st.session_state.current_page = "main"
            st.rerun()
        return

    # Загрузка данных файла из Redis
    files = redis_client.get_all_files()
    if file_index >= len(files):
        st.error("❌ Файл не найден")
        if st.button("← Вернуться назад"):
            st.session_state.current_page = "main"
            st.rerun()
        return

    file_data = files[file_index]
    file_id = file_data.get("file_id")

    logger.info(f"Рендеринг деталей файла: {file_id}")

    # Заголовок
    st.title("📋 Детали файла")

    # Кнопка назад
    if st.button("← Вернуться к реестру"):
        st.session_state.current_page = "main"
        st.session_state.editing_file_index = None
        st.rerun()

    st.divider()

    # Основная информация
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📁 Основная информация")
        st.markdown(f"**ID:** `{file_id}`")
        st.markdown(f"**Имя:** {file_data.get('original_filename', 'Unknown')}")
        st.markdown(f"**Тип:** {file_data.get('file_type', 'unknown')}")
        st.markdown(f"**Размер:** {format_file_size(file_data.get('file_size', 0))}")

    with col2:
        st.markdown("### 📊 Статус обработки")
        status = file_data.get("status", "unknown")
        status_emoji = {
            "uploaded": "🔵", "processing": "🟡",
            "completed": "🟢", "failed": "🔴", "exported": "🟣"
        }.get(status, "⚪")
        st.markdown(f"**Статус:** {status_emoji} {status}")
        st.markdown(f"**Модуль:** `{file_data.get('current_module', '-')}`")
        st.markdown(f"**Создан:** {format_datetime(file_data.get('created_at'))}")
        st.markdown(f"**Обновлён:** {format_datetime(file_data.get('updated_at'))}")

    with col3:
        st.markdown("### 📤 Экспорт в 1С")
        export_status = file_data.get("export_status", "pending")
        export_emoji = {
            "pending": "⏳", "exporting": "🔄",
            "success": "✅", "failed": "❌"
        }.get(export_status, "⚪")
        st.markdown(f"**Статус:** {export_emoji} {export_status}")
        st.markdown(f"**Попыток:** {file_data.get('export_attempts', 0)}")
        if file_data.get("export_error"):
            st.error(f"❌ {file_data.get('export_error')}")

    st.divider()

    # Прогресс по модулям
    st.markdown("### 📈 Прогресс обработки")
    _render_module_progress(file_data)

    st.divider()

    # История обработки
    st.markdown("### 📜 История обработки")
    _render_history(file_data)

    st.divider()

    # Файлы в структуре
    st.markdown("### 📂 Файлы в структуре")
    _render_file_structure(file_id, st.session_state.get("file_service"))

    st.divider()

    # Действия
    st.markdown("### ⚡ Действия")
    _render_actions(file_id, file_data, redis_client)


def _render_module_progress(file_data: Dict[str, Any]) -> None:
    """Рендерит прогресс по модулям."""
    modules = ["preprocess", "ocr", "llm", "export"]
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")

    progress = 0
    status_text = []

    for i, module in enumerate(modules):
        if module in completed:
            progress += 25
            status_text.append(f"✅ {module}")
        elif current == module:
            status_text.append(f"🔄 {module} (в процессе)")
        else:
            status_text.append(f"⏳ {module}")

    st.progress(progress / 100)
    st.caption(" | ".join(status_text))


def _render_history(file_data: Dict[str, Any]) -> None:
    """Рендерит историю обработки."""
    history = file_data.get("history", [])

    if not history:
        st.info("ℹ️ История пуста")
        return

    for record in reversed(history[-20:]):  # Последние 20 записей
        timestamp = record.get("timestamp", "")[:19]
        module = record.get("module", "unknown")
        action = record.get("action", "unknown")
        success = record.get("success", False)
        error = record.get("error")
        duration = record.get("duration_seconds")

        emoji = "✅" if success else "❌"
        duration_str = f" ({duration:.2f}s)" if duration else ""

        st.markdown(f"{emoji} **{timestamp}** — `{module}`: {action}{duration_str}")
        if error:
            st.caption(f"🔴 Ошибка: {error}")


def _render_file_structure(file_id: str, file_service) -> None:
    """Рендерит структуру файлов."""
    if not file_service:
        st.warning("⚠️ FileService не доступен")
        return

    try:
        file_info = file_service.get_file_info(file_id)

        if not file_info:
            st.warning("⚠️ Информация о файле не найдена")
            return

        for folder, info in file_info.get("directories", {}).items():
            with st.expander(f"📁 {folder} ({info['file_count']} файлов)", expanded=False):
                st.caption(f"Путь: `{info['path']}`")
                for filename in info.get("files", []):
                    st.markdown(f"📄 {filename}")
    except Exception as e:
        logger.error(f"Ошибка получения структуры файлов: {e}")
        st.error(f"❌ Ошибка: {e}")


def _render_actions(file_id: str, file_data: Dict[str, Any], redis_client) -> None:
    """Рендерит кнопки действий."""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Перезапустить обработку", use_container_width=True):
            try:
                file_data["status"] = "processing"
                file_data["current_module"] = "preprocess"
                file_data["completed_modules"] = []
                file_data["retry_count"] = file_data.get("retry_count", 0) + 1
                redis_client.set_file_status(file_id, file_data)
                redis_client.push_to_queue("files:preprocess", FileJob(**file_data).to_payload())
                st.success("✅ Обработка перезапущена")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")

    with col2:
        if st.button("📤 Экспортировать в 1С", use_container_width=True,
                     disabled=file_data.get("export_status") == "success"):
            try:
                file_data["export_status"] = "exporting"
                redis_client.set_file_status(file_id, file_data)
                redis_client.push_to_queue("files:export", FileJob(**file_data).to_payload())
                st.success("✅ Экспорт запущен")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")

    with col3:
        if st.button("🗑️ Удалить файл", use_container_width=True, type="secondary"):
            try:
                redis_client.delete_file_status(file_id)
                st.success("✅ Файл удалён")
                st.session_state.current_page = "main"
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")