# ui/components/file_row.py
"""
Компонент: Строка файла в реестре
"""
import streamlit as st
from typing import Dict, Any, Optional
from utils import setup_logger

logger = setup_logger("ui.components.file_row")


def render_file_row(
        file_data: Dict[str, Any],
        index: int,
        state: Any,
        cols: list,
        on_edit: callable = None,
        on_export: callable = None
) -> None:
    """
    Рендерит одну строку реестра файлов.

    Args:
        file_data: Словарь с данными файла
        index: Индекс файла в общем списке
        state: Объект состояния приложения
        cols: Список колонок Streamlit для размещения
        on_edit: Callback для редактирования
        on_export: Callback для экспорта
    """
    try:
        logger.debug(f"Рендеринг строки файла: индекс={index}, имя={file_data.get('Имя файла')}")

        # Дата
        cols[0].markdown(
            f"<span style='color: #666; font-size: 13px;'>{file_data.get('Дата', '')}</span>",
            unsafe_allow_html=True
        )

        # Имя файла
        cols[1].markdown(f"📄 {file_data.get('Имя файла', 'Unknown')}")

        # Статус с цветом
        status = file_data.get('Статус', '')
        status_color = _get_status_color(status)
        cols[2].markdown(
            f"<span style='color: {status_color};'>{status}</span>",
            unsafe_allow_html=True
        )

        # Тип файла
        cols[3].markdown(file_data.get('Тип файла', ''))

        # Метрики с цветом
        _render_metrics(cols[4], file_data.get('Метрики', ''))

        # Ссылка на файл
        cols[5].markdown("📄 [Открыть](#)")

        # Кнопка редактирования
        _render_edit_button(cols[6], index, state, on_edit)

        # Ссылка на XML
        cols[7].markdown("📥 [Скачать XML](#)")

        # Кнопка экспорта
        _render_export_button(cols[8], index, file_data, state, on_export)

    except Exception as e:
        logger.error(f"Ошибка рендеринга строки файла {index}: {e}", exc_info=True)
        cols[1].error(f"Ошибка отображения: {str(e)}")


def _get_status_color(status: str) -> str:
    """Возвращает цвет для статуса файла"""
    status_colors = {
        "🟢 Экспортирован в 1С": "#155724",
        "🟡 Обработка": "#856404",
        "🔴 Требует правки": "#721c24",
        "🔵 Новый": "#004085",
        "🟣 Поправлен": "#5a3d7a"
    }
    return status_colors.get(status, "#333")


def _render_metrics(col, metrics: str) -> None:
    """Рендерит метрики с цветовым кодированием"""
    try:
        metric_val = int(metrics.replace('%', ''))
        if metric_val >= 95:
            color = "#155724"
        elif metric_val >= 80:
            color = "#856404"
        else:
            color = "#721c24"

        col.markdown(
            f"<span style='color: {color}; font-weight: bold;'>{metrics}</span>",
            unsafe_allow_html=True
        )
    except (ValueError, AttributeError):
        col.markdown(metrics)


def _render_edit_button(col, index: int, state: Any, on_edit: callable = None) -> None:
    """Рендерит кнопку редактирования"""
    if col.button("✏️ Править", key=f"edit_btn_{index}", use_container_width=True):
        logger.info(f"Пользователь нажал 'Править' для файла индекс={index}")
        if on_edit:
            on_edit(index)
        else:
            state.navigate("edit", editing_file_index=index)
        st.rerun()


def _render_export_button(
        col,
        index: int,
        file_data: Dict[str, Any],
        state: Any,
        on_export: callable = None
) -> None:
    """Рендерит кнопку экспорта в 1С"""
    is_exported = "Экспортирован" in file_data.get('Статус', '')

    if state.export_pending == index:
        col.warning("⚠️ Файл уже экспортирован. Повторить?")
        c1, c2 = col.columns(2)

        if c1.button("✅ Да", key=f"confirm_{index}", use_container_width=True):
            logger.info(f"Подтверждён повторный экспорт файла индекс={index}")
            if on_export:
                on_export(index, confirm=True)
            else:
                state.export_to_1c(index, confirm=True)
            st.rerun()

        if c2.button("❌ Нет", key=f"cancel_{index}", use_container_width=True):
            logger.debug(f"Отменён повторный экспорт файла индекс={index}")
            state.export_pending = None
            st.rerun()
    else:
        btn_text = "📤 Экспортирован" if is_exported else "📤 Экспортировать"
        btn_type = "secondary" if is_exported else "primary"

        if col.button(btn_text, key=f"export_{index}", use_container_width=True, type=btn_type):
            logger.info(f"Запрошен экспорт файла индекс={index}")
            if on_export:
                on_export(index)
            else:
                state.export_to_1c(index)
            st.rerun()