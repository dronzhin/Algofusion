# ui/utils/components.py
"""
Базовые утилиты для Streamlit-компонентов.
Устраняет дублирование шаблонов рендеринга.
"""

import streamlit as st
from typing import Callable, Optional, Any, List
from contextlib import contextmanager
from shared.utils.logger import setup_logger

logger = setup_logger("ui.utils.components")


@contextmanager
def error_handler(component_name: str, fallback_message: str = "Произошла ошибка"):
    """
    Контекстный менеджер для обработки ошибок в компонентах.

    Пример:
        with error_handler("file_list"):
            # код рендеринга
    """
    try:
        yield
    except Exception as e:
        logger.error(f"Ошибка в компоненте {component_name}: {e}", exc_info=True)
        st.error(f"❌ {fallback_message}: {e}")


def render_section_header(title: str, help_text: Optional[str] = None):
    """Стандартный заголовок секции."""
    if help_text:
        st.subheader(title, help=help_text)
    else:
        st.subheader(title)
    st.divider()


def render_empty_state(message: str, icon: str = "ℹ️"):
    """Стандартное сообщение при отсутствии данных."""
    st.info(f"{icon} {message}")


def render_columns_config(widths: List[int]) -> List[Any]:
    """
    Создаёт колонки с заданными пропорциями.

    Args:
        widths: Список весов колонок, например [2, 3, 2, 2, 2, 1]
    """
    return st.columns(widths)


def render_action_button(
        label: str,
        key: str,
        callback: Optional[Callable] = None,
        disabled: bool = False,
        type: str = "secondary",
        help: Optional[str] = None,
        use_container_width: bool = True
) -> bool:
    """
    Стандартизированная кнопка действия.

    Returns:
        True если кнопка нажата
    """
    return st.button(
        label,
        key=key,
        on_click=callback,
        disabled=disabled,
        type=type,
        help=help,
        use_container_width=use_container_width
    )


def render_metric_card(label: str, value: Any, delta: Optional[str] = None,
                       delta_color: str = "normal", help: Optional[str] = None):
    """Карточка метрики с опциональным дельта-индикатором."""
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help
    )