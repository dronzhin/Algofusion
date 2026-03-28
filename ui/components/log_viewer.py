# ui/components/log_viewer.py
"""
Компонент: Просмотрщик логов.
Использует LOG_STATUS_CONFIG и render_log_badge из formatters.
"""

import streamlit as st
from typing import List, Dict, Optional, Callable

from shared.utils.logger import setup_logger
from ui.utils.constants import UI_CONFIG, LOG_STATUS_CONFIG
from ui.utils.formatters import render_log_badge

logger = setup_logger("ui.components.log_viewer")


def render_log_viewer(
        logs: List[Dict[str, str]],
        title: str = "📋 Журнал событий",
        show_pending_warning: bool = False,
        on_clear: Optional[Callable] = None,
        limit: int = None
) -> None:
    """Отображает список логов с опциями."""
    try:
        with st.container(border=True):
            # Заголовок + кнопка очистки
            header_col, action_col = st.columns([4, 1])
            with header_col:
                st.markdown(f"### {title}")
                if show_pending_warning:
                    st.warning("🔔 Есть новые события!", icon="🔔")

            with action_col:
                if on_clear and logs:
                    if st.button("🧹", key="clear_logs_btn", help="Очистить журнал"):
                        on_clear()
                        st.rerun()

            if not logs:
                from ui.utils.components import render_empty_state
                render_empty_state("Логи пока пустые")
                return

            # Рендеринг записей
            display_limit = limit or UI_CONFIG["max_logs_display"]
            for log in logs[-display_limit:]:
                _render_log_line(log)

            # Футер
            if len(logs) > display_limit:
                st.caption(f"Показано последних {display_limit} из {len(logs)}")

    except Exception as e:
        logger.error(f"Ошибка рендеринга логов: {e}")
        st.warning("⚠️ Не удалось отобразить журнал")


def _render_log_line(log: Dict[str, str]) -> None:
    """Рендерит одну строку лога с использованием готовых утилит."""
    timestamp = log.get("time", "??:??:??")
    status = log.get("status", "INFO")
    message = log.get("msg", "")

    # Используем готовый бейдж из formatters
    badge_html = render_log_badge(status)

    html = f"""
    <div style="
        font-family: monospace;
        margin-bottom: 6px;
        font-size: 12px;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 4px;
    ">
        <span style="color: #888;">{timestamp}</span> 
        {badge_html}
        <span style="color: #333;">{message}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)