# ui/components/file_preview.py
"""
Компонент: Предпросмотр файла.
Использует file_service для получения контента.
"""

import streamlit as st
from typing import Optional, Any

from shared.utils.logger import setup_logger

logger = setup_logger("ui.components.file_preview")


def render_file_preview(
        file_service: Optional[Any],
        file_id: str,
        filename: str,
        preview_type: str = "auto"
) -> None:
    """
    Показывает превью файла в expander.

    Args:
        file_service: Сервис для работы с файлами
        file_id: ID файла
        filename: Имя файла для отображения
        preview_type: "auto" | "ocr" | "image" | "pdf"
    """
    if not file_service:
        st.warning("⚠️ Сервис файлов не доступен")
        return

    # Текстовое превью (OCR)
    if preview_type in ("auto", "ocr"):
        text_preview = file_service.get_text_preview(file_id, "ocr")
        if text_preview:
            with st.expander(f"📄 Превью: {filename}", expanded=True):
                st.code(text_preview, language="text")
            return

    # Метаданные для определения типа
    metadata = file_service.get_file_metadata(file_id)
    if not metadata:
        st.info("📭 Предпросмотр недоступен. Используйте кнопку «Скачать».")
        return

    # Изображение
    if metadata.get("is_image") and preview_type in ("auto", "image"):
        content = file_service.get_file_content(file_id)
        if content:
            with st.expander(f"🖼️ Изображение: {filename}", expanded=True):
                st.image(content, caption=filename)
        return

    # PDF
    if metadata.get("is_pdf") and preview_type in ("auto", "pdf"):
        with st.expander(f"📕 PDF: {filename}", expanded=True):
            st.info("📄 PDF-файлы можно скачать, но предпросмотр ограничен.")
            st.caption(f"Размер: {metadata.get('size_human', '—')}")
        return

    st.info("📭 Предпросмотр недоступен для этого типа файла.")