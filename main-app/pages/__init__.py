# pages/__init__.py
"""
Регистрация страниц приложения
"""

from typing import Callable
import importlib
import logging

logger = logging.getLogger(__name__)

# Регистр страниц
PAGES = {
    "file_info": "pages.file_info",
    "image_rotation": "pages.image_rotation",
    "binary_image": "pages.binary_image",
    "ocr": "pages.ocr",  # ← Новая страница распознавания
}


def get_page_renderer(page_key: str) -> Callable:
    """
    Получение функции рендеринга для страницы

    Args:
        page_key: ключ страницы

    Returns:
        Функция рендеринга
    """

    if page_key not in PAGES:
        raise ValueError(f"Неизвестная страница: {page_key}")

    try:
        # Импорт модуля страницы
        module_path = PAGES[page_key]
        module = importlib.import_module(module_path)

        # Получение функции рендеринга
        if hasattr(module, 'render_page'):
            return module.render_page
        else:
            raise AttributeError(f"Модуль {module_path} не содержит функции render_page")

    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы '{page_key}': {e}", exc_info=True)
        raise

        return default_renderer

    return renderer