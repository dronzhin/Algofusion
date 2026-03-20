# ui/components/file_row.py
import streamlit as st
from core.models import FileRecord, FileStatus


def render_file_row(record: FileRecord, index: int, state, cols: list):
    """Рендерит одну строку реестра файлов"""

    # Статус с цветом
    status_colors = {
        FileStatus.EXPORTED: "#155724",
        FileStatus.PROCESSING: "#856404",
        FileStatus.NEEDS_FIX: "#721c24",
        FileStatus.NEW: "#004085",
        FileStatus.FIXED: "#5a3d7a"
    }
    status_color = status_colors.get(record.status, "#333")

    cols[0].markdown(f"<span style='color: #666; font-size: 13px;'>{record.date}</span>", unsafe_allow_html=True)
    cols[1].markdown(f"📄 {record.filename}")
    cols[2].markdown(f"<span style='color: {status_color};'>{record.status}</span>", unsafe_allow_html=True)
    cols[3].markdown(record.file_type)

    # Метрики с цветом
    if record.metric_value is not None:
        metric_color = "#155724" if record.metric_value >= 95 else "#856404" if record.metric_value >= 80 else "#721c24"
        cols[4].markdown(f"<span style='color: {metric_color}; font-weight: bold;'>{record.metrics}</span>",
                         unsafe_allow_html=True)
    else:
        cols[4].markdown(record.metrics)

    cols[5].markdown("📄 [Открыть](#)")

    # Кнопка редактирования
    if cols[6].button("✏️ Править", key=f"edit_btn_{index}", use_container_width=True):
        state.navigate("edit", editing_file_index=index)
        st.rerun()

    cols[7].markdown("📥 [Скачать XML](#)")

    # Экспорт в 1С
    _render_export_button(cols[8], record, index, state)


def _render_export_button(col, record: FileRecord, index: int, state):
    """Внутренняя функция для кнопки экспорта"""
    is_exported = FileStatus.EXPORTED.value in record.status

    if state.export_pending == index:
        col.warning("⚠️ Файл уже экспортирован. Повторить?")
        c1, c2 = col.columns(2)
        if c1.button("✅ Да", key=f"confirm_{index}", use_container_width=True):
            from core.services.export_service import ExportService
            ExportService.export_file(state, index, confirm=True)
            st.rerun()
        if c2.button("❌ Нет", key=f"cancel_{index}", use_container_width=True):
            state.export_pending = None
            st.rerun()
    else:
        btn_text = "📤 Экспортирован" if is_exported else "📤 Экспортировать"
        btn_type = "secondary" if is_exported else "primary"
        if col.button(btn_text, key=f"export_{index}", use_container_width=True, type=btn_type):
            from core.services.export_service import ExportService
            ExportService.export_file(state, index)
            st.rerun()