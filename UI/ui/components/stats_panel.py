# ui/components/stats_panel.py
"""
Компонент: Панель статистики
"""
import streamlit as st
from typing import Dict, Any
from utils import setup_logger

logger = setup_logger("ui.components.stats_panel")


def render_stats_panel(stats: Dict[str, Any]) -> None:
    """
    Отображает панель с метриками и графиком.

    Args:
        stats: Словарь со статистикой (total, processed, errors, chart_data)
    """
    logger.debug(f"Рендеринг панели статистики: {stats}")

    with st.container(border=True):
        st.subheader("📊 Текущая статистика")

        m1, m2, m3 = st.columns(3)

        with m1:
            st.metric(
                label="Всего файлов",
                value=stats.get("total", "0"),
                delta=stats.get("total_delta", "+0")
            )

        with m2:
            st.metric(
                label="Обработано",
                value=stats.get("processed", "0"),
                delta=stats.get("processed_delta", "+0")
            )

        with m3:
            st.metric(
                label="Ошибки",
                value=stats.get("errors", "0"),
                delta=stats.get("errors_delta", "-0"),
                delta_color="inverse"
            )

        # График
        chart_data = stats.get("chart_data")
        if chart_data is not None:
            try:
                st.line_chart(chart_data)
            except Exception as e:
                logger.error(f"Ошибка отрисовки графика: {e}")
                st.warning("⚠️ Не удалось отобразить график")