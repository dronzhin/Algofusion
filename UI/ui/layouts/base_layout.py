# ui/layouts/base_layout.py
"""
Базовый шаблон компоновки страницы
"""
import streamlit as st
from typing import Optional, Callable
from utils import setup_logger

logger = setup_logger("ui.layouts.base_layout")


def render_base_layout(
        title: str,
        content_fn: Callable,
        sidebar_fn: Optional[Callable] = None,
        show_footer: bool = True
) -> None:
    """
    Рендерит базовый шаблон страницы с заголовком и опциональным сайдбаром.

    Args:
        title: Заголовок страницы
        content_fn: Функция, рендерящая основной контент
        sidebar_fn: Опциональная функция для сайдбара
        show_footer: Показывать ли футер
    """
    logger.debug(f"Рендеринг базового шаблона: title={title}")

    # Настройка страницы (если вызывается первым)
    st.set_page_config(page_title=title, layout="wide")

    # Сайдбар
    if sidebar_fn:
        with st.sidebar:
            sidebar_fn()

    # Основной контент
    content_fn()

    # Футер
    if show_footer:
        _render_footer()


def _render_footer() -> None:
    """Рендерит футер страницы"""
    st.divider()
    st.caption(
        "📌 Algofusion File Processor © 2025 | "
        "Для технической поддержки обратитесь к администратору системы"
    )
    logger.debug("Футер отрендерен")