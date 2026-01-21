from .file_info import render_page as render_file_info
from .binary_image import render_page as render_binary_image
from .image_rotation import render_page as render_image_rotation
import streamlit as st


def get_page_renderer(page_key: str):
    """
    Получить функцию рендеринга для указанной страницы
    """
    page_renderers = {
        "file_info": render_file_info,
        "binary_image": render_binary_image,
        "image_rotation": render_image_rotation
    }

    renderer = page_renderers.get(page_key)
    if renderer is None:
        def default_renderer():
            st.error(f"⚠️ Страница '{page_key}' не найдена")

        return default_renderer

    return renderer