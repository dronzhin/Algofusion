# ui/components/stats_panel.py
"""
Компонент: Панель статистики.
Использует render_metric_card из components.py
"""

import streamlit as st
from typing import Dict, Any

from shared.utils.logger import setup_logger
from ui.utils.components import render_metric_card

logger = setup_logger("ui.components.stats_panel")


def render_stats_panel(stats: Dict[str, Any], show_progress: bool = True) -> None:
    """Рендерит панель с метриками обработки."""
    try:
        # 5 колонок для основных метрик
        m1, m2, m3, m4, m5 = st.columns(5)

        with m1:
            render_metric_card("📁 Всего", stats.get("total", 0))
        with m2:
            render_metric_card("✅ Завершено", stats.get("completed", 0))
        with m3:
            render_metric_card("⏳ В обработке", stats.get("processing", 0))
        with m4:
            render_metric_card("❌ Ошибки", stats.get("failed", 0), delta_color="inverse")
        with m5:
            render_metric_card("📤 Экспорт", stats.get("exported", 0))

        # Прогресс-бар успешности
        if show_progress:
            success_rate = stats.get("success_rate", "0%")
            try:
                rate_value = float(success_rate.replace("%", ""))
                st.progress(rate_value / 100)
                st.caption(f"✨ Успешность: {success_rate}")
            except (ValueError, TypeError):
                st.caption(f"✨ Успешность: {success_rate}")

    except Exception as e:
        logger.error(f"Ошибка рендеринга статистики: {e}")
        st.warning("⚠️ Не удалось отобразить статистику")