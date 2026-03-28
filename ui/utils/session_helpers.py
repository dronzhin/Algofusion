# ui/utils/session_helpers.py
"""
Утилиты для работы с session_state.
Централизует паттерны инициализации и доступа к настройкам.
"""

from typing import Any, TypeVar, Callable
from shared.utils.logger import setup_logger
from shared.config.settings import get_settings

logger = setup_logger("ui.utils.session_helpers")

T = TypeVar("T")


def get_settings_safe(session_state: Any) -> Any:
    """
    Безопасное получение настроек: session.settings → глобальный get_settings().

    Универсальный fallback-паттерн для компонентов.
    """
    if hasattr(session_state, "settings") and session_state.settings is not None:
        return session_state.settings
    logger.debug("⚠️ session.settings не инициализирован, используем глобальный get_settings()")
    return get_settings()


def generate_prefixed_keys(prefix: str, *suffixes: str) -> tuple[str, ...]:
    """
    Генерация ключей для session_state с префиксом.

    Пример:
        >>> generate_prefixed_keys("main", "enabled", "interval")
        ("main_enabled", "main_interval")
    """
    return tuple(f"{prefix}_{s}" for s in suffixes)


def init_session_defaults(
        session_state: dict,
        defaults: dict[str, Any],
        keys: tuple[str, ...] | None = None
) -> None:
    """
    Инициализация дефолтов в session_state (только если ключей ещё нет).

    Args:
        session_state: Обычно st.session_state
        defaults: Словарь {key: default_value}
        keys: Опционально, подмножество ключей для инициализации
    """
    keys_to_init = keys if keys is not None else defaults.keys()
    for key in keys_to_init:
        if key not in session_state and key in defaults:
            session_state[key] = defaults[key]


def validate_range(value: T, min_val: T, max_val: T, clamp: bool = True) -> T:
    """
    Валидация значения в диапазоне [min, max].

    Args:
        value: Проверяемое значение
        min_val: Минимальное допустимое
        max_val: Максимальное допустимое
        clamp: Если True — «прижимает» значение к границам, если False — бросает ошибку

    Returns:
        Валидированное значение

    Raises:
        ValueError: Если значение вне диапазона и clamp=False
    """
    if clamp:
        return max(min_val, min(value, max_val))
    if not (min_val <= value <= max_val):
        raise ValueError(f"Значение {value} вне диапазона [{min_val}, {max_val}]")
    return value