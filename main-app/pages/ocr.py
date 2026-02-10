# pages/ocr.py
"""
Страница распознавания текста с полной интеграцией существующего error_handler.py
"""

import streamlit as st
from services.ocr_client import OCRClient
from services.preprocessing_client import PreprocessingClient
from components import FilePreviewComponent, OCRResultComponent
from components.error_handler import error_handler
from state import SessionManager
from utils import get_file_icon


def render_page():
    """Основная функция рендеринга страницы распознавания текста"""

    st.subheader("🔍 Распознавание текста с изображений и документов")

    # Инициализация клиентов
    ocr_client = OCRClient()
    preprocessing_client = PreprocessingClient()

    # Проверка доступности серверов
    _check_server_availability(ocr_client, preprocessing_client)

    # Проверка наличия файла
    shared_file = SessionManager.get_shared_file()
    if not shared_file:
        st.warning("⚠️ Сначала загрузите файл во вкладке 'Информация о файле'")
        return

    # Проверка поддержки формата (включая PDF)
    if not _is_supported_file(shared_file):
        _show_unsupported_file_error(shared_file)
        return

    # # Отображение информации о файле и превью (как на других страницах)
    # _show_file_info_and_preview(shared_file)

    # Получение списка моделей и выбор
    models_info = ocr_client.get_available_models()
    model_name = OCRResultComponent.show_model_selection(models_info)

    # Настройки распознавания
    prompt, return_confidence = _render_settings()

    # Кнопка распознавания
    if st.button("🔍 Распознать текст", type="primary", key="ocr_start_button"):
        _process_ocr(shared_file, ocr_client, model_name, prompt, return_confidence)

    # Отображение результатов
    _display_results(shared_file["name"])


def _check_server_availability(ocr_client, preprocessing_client):
    """Проверка и отображение статуса серверов"""
    col1, col2 = st.columns(2)

    with col1:
        if ocr_client.health_check():
            st.success("✅ Сервер распознавания доступен (порт 8000)")
        else:
            OCRResultComponent.show_server_unavailable(
                server_name="распознавания текста",
                server_url=ocr_client.base_url,
                port=8000
            )

    with col2:
        if preprocessing_client.health_check():
            st.success("✅ Сервер предобработки доступен (порт 8001)")
        else:
            st.info("ℹ️ Сервер предобработки недоступен (бинаризация/поворот будут ограничены)")


def _is_supported_file(shared_file: dict) -> bool:
    """Проверка поддержки формата файла"""
    valid_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.pdf']
    return any(shared_file["name"].lower().endswith(ext) for ext in valid_exts)


def _show_unsupported_file_error(shared_file: dict):
    """Отображение ошибки неподдерживаемого формата"""
    valid_exts = ['JPG', 'PNG', 'BMP', 'TIFF', 'WEBP', 'PDF']
    st.warning(
        f"⚠️ Формат файла '{shared_file['name']}' не поддерживается для распознавания текста. "
        f"Поддерживаются форматы: {', '.join(valid_exts)}"
    )


def _show_file_info_and_preview(shared_file: dict):
    """Отображение информации о файле и превью как на других страницах"""
    icon = get_file_icon(shared_file["type"], shared_file["ext"])
    file_type = "PDF-документ" if shared_file["name"].lower().endswith('.pdf') else "изображение"

    st.info(f"{icon} Работаем с {file_type}: **{shared_file['name']}**")

    # ПРАВИЛЬНЫЙ ВЫЗОВ КОМПОНЕНТА (без комментариев!)
    FilePreviewComponent.render(
        file_bytes=shared_file["bytes"],
        file_type=shared_file["type"],
        file_name=shared_file["name"],
        file_ext=shared_file["ext"],
        title="📥 Исходный файл",
        show_meta=True
    )


def _render_settings():
    """Отображение настроек распознавания"""
    with st.expander("⚙️ Настройки распознавания", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            prompt = st.text_area(
                "Промпт для модели:",
                value="Extract all text preserving structure",
                height=80,
                help="Инструкция для модели. На английском языке."
            )

        with col2:
            return_confidence = st.checkbox(
                "Возвращать метрику уверенности",
                value=True,
                help="Замедляет обработку на 20-30%, но даёт оценку качества распознавания"
            )

    return prompt, return_confidence


def _process_ocr(shared_file, ocr_client, model_name, prompt, return_confidence):
    """Обработка распознавания текста с интеграцией существующего обработчика ошибок"""
    with st.spinner(f"🔍 Распознавание текста с помощью {model_name}..."):
        try:
            # Вызов клиента с выбрасыванием специализированных исключений
            result = ocr_client.recognize_text(
                file_data=shared_file["bytes"],
                filename=shared_file["name"],
                model_name=model_name,
                prompt=prompt,
                return_confidence=return_confidence
            )

            # Сохранение результата
            SessionManager.set_ocr_results(result)

            # Успешное сообщение через существующий обработчик
            pages_info = f"Обработано {result.get('total_pages', 1)} страниц" if result.get(
                'file_type') == 'pdf' else "Текст успешно распознан"
            error_handler.show_success_message(pages_info, operation_name="распознавание текста")

        except Exception as e:
            # Обработка ошибки через существующий обработчик
            error_handler.handle_api_error(e, operation_name="распознавание текста")


def _display_results(original_filename: str):
    """Отображение результатов распознавания"""
    ocr_results = SessionManager.get_ocr_results()

    if not ocr_results:
        st.info("👆 Нажмите кнопку 'Распознать текст' для запуска обработки")
        return

    # Отображение результата с оригинальным документом и ответом сервера
    OCRResultComponent.render_ocr_result(ocr_results, original_filename)