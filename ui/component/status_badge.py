# ui/components/status_badge.py
"""
Компонент: Бейдж статуса файла.
"""

import streamlit as st


def render_status_badge(status: str) -> str:
    """Возвращает HTML для бейджа статуса."""
    status_config = {
        "uploaded": {"emoji": "🔵", "color": "#004085", "bg": "#cce5ff"},
        "processing": {"emoji": "🟡", "color": "#856404", "bg": "#fff3cd"},
        "completed": {"emoji": "🟢", "color": "#155724", "bg": "#d4edda"},
        "failed": {"emoji": "🔴", "color": "#721c24", "bg": "#f8d7da"},
        "exported": {"emoji": "🟣", "color": "#5a3d7a", "bg": "#e2d5f1"},
    }

    config = status_config.get(status, {"emoji": "⚪", "color": "#333", "bg": "#f0f0f0"})

    return f"""
    <span style="
        background-color: {config['bg']};
        color: {config['color']};
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    ">
        {config['emoji']} {status}
    </span>
    """