"""
Утилиты форматирования для UI.
Централизует отображение дат, статусов и текста.
"""

from datetime import datetime
from typing import Optional, Union
import streamlit as st

from shared.utils.logger import setup_logger
from ui.utils.constants import FILE_STATUS_CONFIG, UI_CONFIG, LOG_STATUS_CONFIG, EXPORT_STATUS_CONFIG

logger = setup_logger("ui.utils.formatters")


def format_datetime_short(dt: Optional[Union[datetime, str]]) -> str:
    """Форматирование даты/времени в коротком формате."""
    if dt is None:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    return dt.strftime(UI_CONFIG["datetime_format_short"])


def format_datetime_full(dt: Optional[Union[datetime, str]]) -> str:
    """Форматирование даты/времени в полном формате."""
    if dt is None:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    return dt.strftime(UI_CONFIG["datetime_format_full"])


def format_file_size_human(size_bytes: Optional[int]) -> str:
    """Форматирование размера файла (алиас с обработкой None)."""
    if size_bytes is None:
        return "-"
    if size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла в человекочитаемый вид."""
    return format_file_size_human(size_bytes)


def render_status_badge(status: str, with_tooltip: bool = True, size: str = "normal") -> str:
    """
    Возвращает HTML для стилизованного бейджа статуса файла.

    ⚠️ Рендерить с unsafe_allow_html=True или использовать render_status_badge_safe()
    """
    config = FILE_STATUS_CONFIG.get(status, FILE_STATUS_CONFIG["uploaded"])
    emoji = config["emoji"]
    label = config["label"]
    color = config["color"]
    bg = config["bg"]

    sizes = {
        "small": {"padding": "2px 6px", "font_size": "10px", "radius": "8px"},
        "normal": {"padding": "4px 10px", "font_size": "11px", "radius": "12px"},
        "large": {"padding": "6px 14px", "font_size": "13px", "radius": "16px"},
    }
    style = sizes.get(size, sizes["normal"])
    tooltip = f' title="{label}"' if with_tooltip else ''

    return f'''
    <span style="
        background-color:{bg};
        color:{color};
        padding:{style["padding"]};
        border-radius:{style["radius"]};
        font-weight:600;
        font-size:{style["font_size"]};
        display:inline-block;
        white-space:nowrap;
        box-shadow:0 1px 2px rgba(0,0,0,0.1);
        transition:transform 0.1s ease;
    "{tooltip} onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
        {emoji} {label}
    </span>
    '''.strip()


def render_status_badge_safe(status: str, container, with_tooltip: bool = True, size: str = "normal"):
    """Безопасный рендеринг бейджа статуса в Streamlit."""
    html_code = render_status_badge(status, with_tooltip=with_tooltip, size=size)
    container.markdown(html_code, unsafe_allow_html=True)


def render_export_badge(status: str) -> str:
    """Возвращает HTML для бейджа статуса экспорта в 1С."""
    config = EXPORT_STATUS_CONFIG.get(status, EXPORT_STATUS_CONFIG["pending"])
    emoji = config["emoji"]
    label = config["label"]

    colors = {
        "pending": ("#6c757d", "#e9ecef"),
        "exporting": ("#856404", "#fff3cd"),
        "success": ("#155724", "#d4edda"),
        "failed": ("#721c24", "#f8d7da"),
    }
    color, bg = colors.get(status, colors["pending"])

    return f'''
    <span style="
        background-color:{bg};
        color:{color};
        padding:3px 8px;
        border-radius:10px;
        font-weight:500;
        font-size:11px;
        display:inline-block;
    ">
        {emoji} {label}
    </span>
    '''.strip()


def render_export_badge_safe(status: str, container):
    """Безопасный рендеринг бейджа экспорта."""
    html_code = render_export_badge(status)
    container.markdown(html_code, unsafe_allow_html=True)


def render_export_status_badge(status: str, with_tooltip: bool = True) -> str:
    """
    Возвращает HTML для бейджа статуса экспорта в 1С.
    Алиас для render_export_badge с явным именем.

    ⚠️ Рендерить с unsafe_allow_html=True
    """
    return render_export_badge(status)


def render_export_status_badge_safe(status: str, container, with_tooltip: bool = True):
    """Безопасный рендеринг бейджа статуса экспорта в Streamlit."""
    html_code = render_export_status_badge(status, with_tooltip=with_tooltip)
    container.markdown(html_code, unsafe_allow_html=True)


def render_log_badge(status: str) -> str:
    """Возвращает HTML для бейджа статуса лога."""
    config = LOG_STATUS_CONFIG.get(status, LOG_STATUS_CONFIG["INFO"])
    emoji = config["emoji"]
    color = config["color"]
    return f'<span style="color:{color};font-weight:bold;">{emoji} {status}</span>'


def truncate_filename(filename: str, max_length: int = 30, suffix: str = "...") -> str:
    """Обрезка имени файла с суффиксом."""
    if len(filename) <= max_length:
        return filename
    prefix_len = (max_length - len(suffix)) // 2
    suffix_len = max_length - len(suffix) - prefix_len
    return f"{filename[:prefix_len]}{suffix}{filename[-suffix_len:]}"


def calculate_module_progress(completed: set, current: Optional[str]) -> tuple[int, list[str]]:
    """Расчёт прогресса обработки файла по модулям."""
    from ui.utils.constants import MODULES_ORDER

    total = len(MODULES_ORDER)
    completed_count = len(completed)

    if current and current not in completed:
        progress = min((completed_count + 0.5) / total * 100, 99)
    else:
        progress = (completed_count / total * 100) if total > 0 else 0

    status_texts = []
    for module in MODULES_ORDER:
        if module in completed:
            status_texts.append(f"✅ {module}")
        elif module == current:
            status_texts.append(f"🔄 {module}")
        else:
            status_texts.append(f"⏳ {module}")

    return int(progress), status_texts


# ============================================================================
# PUBLIC API - Явный экспорт функций для импорта
# ============================================================================

__all__ = [
    "format_datetime_short",
    "format_datetime_full",
    "format_file_size",
    "format_file_size_human",
    "render_status_badge",
    "render_status_badge_safe",
    "render_export_badge",
    "render_export_badge_safe",
    "render_export_status_badge",       # ← Явно экспортируем!
    "render_export_status_badge_safe",  # ← Явно экспортируем!
    "render_log_badge",
    "truncate_filename",
    "calculate_module_progress",
]