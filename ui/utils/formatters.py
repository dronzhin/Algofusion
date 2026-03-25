# ui/utils/formatters.py
"""
Утилиты форматирования для UI.
Централизует логику отображения данных.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from ui.utils.constants import (
    FILE_STATUS_CONFIG,
    EXPORT_STATUS_CONFIG,
    LOG_STATUS_CONFIG,
    UI_CONFIG,
    MODULES_ORDER
)


def format_datetime_short(dt_value: Optional[str]) -> str:
    """Короткий формат даты для таблиц."""
    if not dt_value:
        return "-"
    try:
        if isinstance(dt_value, str):
            dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
        else:
            dt = dt_value
        return dt.strftime(UI_CONFIG["datetime_format_short"])
    except (ValueError, AttributeError):
        return str(dt_value)[:16] if dt_value else "-"


def format_datetime_full(dt_value: Optional[str]) -> str:
    """Полный формат даты для деталей."""
    if not dt_value:
        return "-"
    try:
        if isinstance(dt_value, str):
            dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
        else:
            dt = dt_value
        return dt.strftime(UI_CONFIG["datetime_format_full"])
    except (ValueError, AttributeError):
        return str(dt_value)[:19] if dt_value else "-"


def render_status_badge(status: str, config: Optional[Dict] = None) -> str:
    """
    Генерирует HTML для бейджа статуса.

    Args:
        status: Ключ статуса (uploaded, processing, etc.)
        config: Опционально кастомная конфигурация
    """
    cfg = config or FILE_STATUS_CONFIG.get(status, {"emoji": "⚪", "color": "#333", "bg": "#f0f0f0"})
    return f"""
    <span style="
        background-color: {cfg['bg']};
        color: {cfg['color']};
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
        display: inline-block;
    ">
        {cfg['emoji']} {cfg.get('label', status)}
    </span>
    """


def render_export_status_badge(status: str) -> str:
    """Бейдж для статуса экспорта."""
    cfg = EXPORT_STATUS_CONFIG.get(status, {"emoji": "⚪", "label": status})
    return f"<strong>{cfg['emoji']} {cfg['label']}</strong>"


def render_log_line_html(timestamp: str, status: str, message: str) -> str:
    """HTML для строки лога."""
    cfg = LOG_STATUS_CONFIG.get(status, {"emoji": "ℹ️", "color": "#6c757d"})
    return f"""
    <div style="
        font-family: monospace;
        margin-bottom: 6px;
        font-size: 12px;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 4px;
    ">
        <span style="color: #888;">{timestamp}</span> 
        <span style="color: {cfg['color']}; font-weight: bold;">{cfg['emoji']} {status}</span> 
        <span style="color: #333;">{message}</span>
    </div>
    """


def calculate_module_progress(completed_modules: list, current_module: Optional[str] = None) -> tuple[int, list[str]]:
    """
    Рассчитывает прогресс по модулям.

    Returns:
        (progress_percent: 0-100, status_texts: list[str])
    """
    progress = 0
    status_texts = []

    for module in MODULES_ORDER:
        if module in completed_modules:
            progress += 25
            status_texts.append(f"✅ {module}")
        elif current_module == module:
            status_texts.append(f"🔄 {module}")
        else:
            status_texts.append(f"⏳ {module}")

    return min(progress, 100), status_texts


def truncate_filename(filename: str, max_length: int = 30) -> str:
    """Обрезает имя файла для отображения в таблице."""
    if len(filename) <= max_length:
        return filename
    name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
    return f"{name[:max_length - len(ext) - 3]}...{ext}"


def format_file_size_human(size_bytes: int) -> str:
    """Человекочитаемый размер файла."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"