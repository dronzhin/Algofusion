# ui/components/file_detail/progress.py
import streamlit as st
from typing import Dict, Any
from ui.utils.constants import MODULES_ORDER
from ui.utils.formatters import calculate_module_progress

def render_progress_section(file_data: Dict[str, Any]) -> None:
    completed = set(file_data.get("completed_modules", []))
    current = file_data.get("current_module")
    progress, status_texts = calculate_module_progress(completed, current)
    st.progress(progress / 100)
    st.caption(" | ".join(status_texts))
    with st.expander("🔍 Детали по модулям", expanded=False):
        for module in MODULES_ORDER:
            if module in completed: st.markdown(f"✅ **{module}** — завершён")
            elif current == module: st.markdown(f"🔄 **{module}** — выполняется")
            else: st.markdown(f"⏳ **{module}** — ожидает")