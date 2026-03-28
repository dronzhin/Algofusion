# ui/components/refresh_settings.py
"""
Компонент: Настройки автообновления страницы.
Работает с интервалами в секундах (5-60 сек).
"""

import streamlit as st
from typing import Any

from shared.utils.logger import setup_logger
from ui.utils.session_helpers import (
    get_settings_safe,
    generate_prefixed_keys,
    validate_range,
)

logger = setup_logger("ui.components.refresh_settings")


def _get_refresh_defaults(settings: Any) -> dict[str, Any]:
    """Получение дефолтов для настроек автообновления (в секундах)."""
    return {
        "enabled": getattr(settings, "ui_auto_refresh_enabled", True),
        "interval_sec": getattr(settings, "ui_auto_refresh_interval_sec", 5),
        "min_sec": getattr(settings, "ui_auto_refresh_min_sec", 5),
        "max_sec": getattr(settings, "ui_auto_refresh_max_sec", 60),
    }


def _seconds_to_ms(seconds: int) -> int:
    """Конвертация секунд в миллисекунды для st_autorefresh."""
    return seconds * 1000


def render_refresh_settings(
    session_state: Any,
    key_prefix: str = "main"
) -> tuple[bool, int]:
    """
    Рендерит настройки автообновления в sidebar.

    Returns:
        tuple[bool, int]: (enabled, interval_sec) — настройки в секундах
    """
    settings = get_settings_safe(session_state)

    # 🔹 Генерация ключей
    enabled_key, interval_key = generate_prefixed_keys(
        key_prefix,
        "auto_refresh_enabled",
        "auto_refresh_interval_sec"  # ← ключ теперь с суффиксом _sec
    )

    # 🔹 Получение дефолтов
    defaults = _get_refresh_defaults(settings)

    # 🔹 Инициализация st.session_state (если ключей ещё нет)
    if enabled_key not in st.session_state:
        st.session_state[enabled_key] = defaults["enabled"]
    if interval_key not in st.session_state:
        st.session_state[interval_key] = defaults["interval_sec"]

    with st.expander("🔄 Автообновление", expanded=False):
        # Toggle: вкл/выкл
        auto_refresh_enabled = st.toggle(
            "Включить автообновление",
            value=st.session_state[enabled_key],
            key=f"toggle_{key_prefix}_refresh",
            help="Автоматически обновлять данные на странице"
        )
        st.session_state[enabled_key] = auto_refresh_enabled

        # Slider: интервал в секундах (5-60)
        current_sec = st.session_state[interval_key]
        safe_value = validate_range(current_sec, defaults["min_sec"], defaults["max_sec"])

        auto_refresh_interval_sec = st.slider(
            "Период обновления (сек)",  # ← подпись в секундах
            min_value=defaults["min_sec"],
            max_value=defaults["max_sec"],
            value=safe_value,
            step=1,                       # ← шаг 1 секунда
            key=f"slider_{key_prefix}_refresh",
            disabled=not auto_refresh_enabled,
            help="Интервал между автоматическими обновлениями страницы"
        )
        st.session_state[interval_key] = auto_refresh_interval_sec

        # Human-readable hint
        st.caption(f"⏱️ Обновление каждые {auto_refresh_interval_sec} сек")

        # Reset к дефолтам
        if st.button("🔄 Сбросить", key=f"btn_reset_{key_prefix}_refresh", use_container_width=True):
            st.session_state[enabled_key] = defaults["enabled"]
            st.session_state[interval_key] = defaults["interval_sec"]
            st.rerun()

        # Возвращаем настройки в секундах
        return auto_refresh_enabled, auto_refresh_interval_sec


def get_refresh_config(session_state: Any, key_prefix: str = "main") -> tuple[bool, int]:
    """
    Возвращает актуальные настройки автообновления.

    Returns:
        tuple[bool, int]: (enabled, interval_sec) — в секундах
    """
    settings = get_settings_safe(session_state)

    enabled_key, interval_key = generate_prefixed_keys(
        key_prefix,
        "auto_refresh_enabled",
        "auto_refresh_interval_sec"
    )

    defaults = _get_refresh_defaults(settings)

    enabled = st.session_state.get(enabled_key, defaults["enabled"])
    interval_sec = st.session_state.get(interval_key, defaults["interval_sec"])

    # Валидация на лету
    interval_sec = validate_range(interval_sec, defaults["min_sec"], defaults["max_sec"])

    return enabled, interval_sec