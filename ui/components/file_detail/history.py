# ui/components/file_detail/history.py
import streamlit as st
from typing import Dict, Any
from ui.utils.constants import UI_CONFIG
from ui.utils.formatters import format_datetime_full
from ui.utils.components import render_empty_state

def render_history_section(file_data: Dict[str, Any]) -> None:
    history = file_data.get("history", [])
    if not history:
        render_empty_state("История пуста — обработка ещё не начиналась")
        return
    for record in reversed(history[-UI_CONFIG["max_logs_display"]:]):
        timestamp = format_datetime_full(record.get("timestamp"))
        emoji = "✅" if record.get("success") else "❌"
        duration = f" ({record.get('duration_seconds', 0):.2f}с)" if record.get("duration_seconds") else ""
        st.markdown(f"{emoji} **{timestamp}** — `{record.get('module')}`: {record.get('action')}{duration}")
        if record.get("error"): st.caption(f"🔴 Ошибка: {record['error']}")