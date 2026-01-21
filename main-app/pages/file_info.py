import streamlit as st
from services.file_service import FileService
from components.file_preview import FilePreviewComponent
from state.session_manager import SessionManager
from utils import get_file_metadata, get_file_icon, handle_file_error, handle_image_processing_error
from typing import Any, Dict


def render_page():
    """
    Страница информации о файле
    """
    st.subheader(f"{get_file_icon('generic', '.txt')} Анализ файла")

    # Загрузка файла
    uploaded_file = st.file_uploader("Загрузите файл", type=["pdf", "jpg", "jpeg", "png", "bmp", "gif", "docx"],
                                     key="main_file_uploader")

    # Обработка загрузки файла
    if uploaded_file is not None:
        _process_uploaded_file(uploaded_file)
    else:
        SessionManager.clear_shared_file()
        st.info("👆 Пожалуйста, загрузите файл для анализа")


def _process_uploaded_file(uploaded_file):
    """
    Обработка загруженного файла
    """
    try:
        # Обработка файла через сервис
        file_info = FileService.process_uploaded_file(uploaded_file)

        if file_info is None:
            st.warning("⚠️ Файл не прошел валидацию. Пожалуйста, загрузите другой файл.")
            return

        # Получение метаданных
        metadata = get_file_metadata(uploaded_file)

        # Сохранение в сессию
        SessionManager.set_shared_file(file_info)

        # Отображение информации о файле
        _show_file_info(metadata, file_info)

        # Отображение предпросмотра
        _show_file_preview(file_info, metadata)

    except Exception as e:
        handle_file_error(e, uploaded_file.name if uploaded_file else "неизвестный файл")


def _show_file_info(metadata: Dict[str, Any], file_info: Dict[str, Any]):
    """
    Отображение информации о файле
    """
    with st.expander("📋 Информация о файле", expanded=True):
        col1, col2 = st.columns([1, 1])

        with col1:
            icon = get_file_icon(file_info["type"], file_info["ext"])
            st.markdown(f"### {icon} {metadata['name']}")
            st.metric("Размер", f"{metadata['size_mb']} MB")
            st.metric("Тип", file_info["type"])

        with col2:
            st.metric("Расширение", metadata["ext"].upper())
            if metadata["is_image"]:
                st.success("✅ Это изображение")
            elif metadata["is_pdf"]:
                st.success("✅ Это PDF документ")
            elif metadata["is_docx"]:
                st.success("✅ Это Word документ")
            else:
                st.warning("⚠️ Формат может не поддерживаться для некоторых операций")

        # Дополнительная информация
        st.markdown("---")
        st.markdown("**Доступные операции:**")

        supported_operations = []
        if metadata["is_image"] or metadata["is_pdf"]:
            supported_operations.extend([
                "Выравнивание изображения",
                "Конвертация в бинарный формат"
            ])

        if metadata["is_pdf"] or metadata["is_docx"]:
            supported_operations.append("OCR распознавание (в разработке)")

        if supported_operations:
            for operation in supported_operations:
                st.markdown(f"- ✅ {operation}")
        else:
            st.markdown("- ❌ Нет доступных операций для этого типа файла")


def _show_file_preview(file_info: Dict[str, Any], metadata: Dict[str, Any]):
    """
    Отображение предпросмотра файла
    """
    st.markdown("---")
    st.subheader("🔍 Предпросмотр файла")

    try:
        # Универсальное отображение предпросмотра
        FilePreviewComponent.render(
            file_bytes=file_info["bytes"],
            file_type=file_info["type"],
            file_name=file_info["name"],
            file_ext=file_info["ext"],
            title=f"📥 Исходный файл: {file_info['name']}",
            show_metadata=True
        )

    except Exception as e:
        handle_image_processing_error(e, "предпросмотр файла")
        st.info("Предпросмотр недоступен для этого типа файла.")