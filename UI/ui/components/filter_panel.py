# ui/components/filter_panel.py
"""
Компонент: Панель фильтров
"""
import streamlit as st
from datetime import date
from typing import Optional, Tuple, Dict, Any
from utils import setup_logger

logger = setup_logger("ui.components.filter_panel")


def render_filter_panel(state: Any) -> Tuple[Optional[date], int, str]:
    """
    Отображает панель фильтров и возвращает выбранные значения.

    Returns:
        filter_date: Выбранная дата или None
        accuracy_threshold: Порог точности
        accuracy_type: Тип фильтра ('sidebar' или 'manual')
    """
    logger.debug("Рендеринг панели фильтров")

    with st.container(border=True):
        st.markdown("### 🔍 Фильтры")

        filter_col1, filter_col2, filter_col3 = st.columns(3)

        # Фильтр по дате
        filter_date = _render_date_filter(filter_col1, state)

        # Тип фильтра точности
        accuracy_type = _render_accuracy_type_filter(filter_col2, state)

        # Фильтр по точности
        accuracy_threshold = _render_accuracy_filter(filter_col3, state, accuracy_type)

        # Кнопки управления
        _render_filter_controls(state)

        # Отображение активных фильтров
        _render_active_filters(state, filter_date, accuracy_threshold, accuracy_type)

    return filter_date, accuracy_threshold, accuracy_type


def _render_date_filter(col, state: Any) -> Optional[date]:
    """Рендерит фильтр по дате"""
    col.markdown("**📅 Фильтр по дате**")
    filter_date = col.date_input(
        "Выберите дату",
        value=state.filter_date,
        key=f"filter_date_input_{state.filter_reset_counter}",
        help="Оставьте пустым для отображения всех дат"
    )
    state.filter_date = filter_date
    logger.debug(f"Фильтр по дате: {filter_date}")
    return filter_date


def _render_accuracy_type_filter(col, state: Any) -> str:
    """Рендерит переключатель типа фильтра точности"""
    col.markdown("**🎯 Источник точности**")
    radio_index = 0 if state.filter_accuracy_type == 'sidebar' else 1

    accuracy_type = col.radio(
        "Источник значения",
        ["Установленные значения", "Ручной ввод"],
        index=radio_index,
        key=f"accuracy_type_radio_{state.filter_reset_counter}",
        horizontal=True
    )

    state.filter_accuracy_type = 'sidebar' if accuracy_type == "Установленные значения" else 'manual'
    logger.debug(f"Тип фильтра точности: {state.filter_accuracy_type}")
    return state.filter_accuracy_type


def _render_accuracy_filter(col, state: Any, accuracy_type: str) -> int:
    """Рендерит фильтр по точности"""
    col.markdown("**📊 Максимальная точность**")
    threshold = 100

    if accuracy_type == 'sidebar':
        sidebar_acc = state.get('sidebar_accuracy', 'Средняя точность (>95%)')
        mapping = {
            "Высокая точность (>98%)": 98,
            "Средняя точность (>95%)": 95,
            "Низкая точность (>90%)": 90
        }
        threshold = mapping.get(sidebar_acc, 95)
        col.info(f"≤{threshold}% (из настроек)")
        state.filter_accuracy_manual = threshold
    else:
        threshold = col.slider(
            "Максимальный процент",
            min_value=0,
            max_value=100,
            value=state.filter_accuracy_manual,
            key=f"accuracy_slider_{state.filter_reset_counter}"
        )
        state.filter_accuracy_manual = threshold
        col.markdown(f"≤**{threshold}%**")

    logger.debug(f"Порог точности: {threshold}%")
    return threshold


def _render_filter_controls(state: Any) -> None:
    """Рендерит кнопки управления фильтрами"""
    filter_btn_col1, _ = st.columns(2)
    with filter_btn_col1:
        if st.button("🔄 Сбросить фильтры", use_container_width=True, key="reset_filters_btn"):
            logger.info("Пользователь сбросил фильтры")
            state.filter_reset_counter += 1
            state.filter_date = None
            state.filter_accuracy_manual = 100
            state.filter_accuracy_type = 'manual'
            st.rerun()


def _render_active_filters(
        state: Any,
        filter_date: Optional[date],
        accuracy_threshold: int,
        accuracy_type: str
) -> None:
    """Отображает строку с активными фильтрами"""
    active_filters = []

    if filter_date is not None:
        active_filters.append(f"📅 Дата: {filter_date.strftime('%d.%m.%Y')}")

    if accuracy_threshold < 100:
        active_filters.append(f"🎯 Точность: ≤{accuracy_threshold}%")

    if active_filters:
        st.success("✅ Активные фильтры: " + " | ".join(active_filters))
    else:
        st.info("ℹ️ Фильтры не применены — отображаются все файлы")