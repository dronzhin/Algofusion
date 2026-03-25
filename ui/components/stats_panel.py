# ui/components/stats_panel.py
"""
Компонент: Панель статистики.
"""

import streamlit as st
from typing import Dict, Any
from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.stats_panel")


def render_stats_panel(stats: Dict[str, Any]) -> None:
    """Рендерит панель с метриками."""
    try:
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric(
                label="Всего файлов",
                value=stats.get("total", 0),
                delta=None
            )

        with m2:
            st.metric(
                label="Успешно",
                value=stats.get("completed", 0),
                delta=f"{stats.get('success_rate', '0%')} успех"
            )

        with m3:
            st.metric(
                label="В обработке",
                value=stats.get("processing", 0),
                delta=None,
                delta_color="normal"
            )

        with m4:
            st.metric(
                label="Ошибки",
                value=stats.get("failed", 0),
                delta=None,
                delta_color="inverse"
            )

        # Дополнительная строка с экспортом
        e1, e2 = st.columns(2)

        with e1:
            st.metric(
                label="Экспортировано в 1С",
                value=stats.get("exported", 0),
                delta=f"{stats.get('export_rate', '0%')} от всех"
            )

        with e2:
            st.metric(
                label="Ожидают экспорта",
                value=stats.get("export_pending", 0),
                delta=None
            )

    except Exception as e:
        logger.error(f"Ошибка рендеринга статистики: {e}")
        st.warning("⚠️ Не удалось отобразить статистику")