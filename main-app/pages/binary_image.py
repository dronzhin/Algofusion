# pages/binary_image.py
import streamlit as st
from services import APIClient
from components import FilePreviewComponent, SettingsPanel, show_unsupported_file_error, handle_api_error, show_download_button
from state import SessionManager
import base64
from config import Config


def render_page():
    """Основная функция рендеринга страницы"""
    st.subheader("🖨️ Конвертер в чёрно-белое (бинарное) изображение")

    # Проверка наличия файла
    shared_file = SessionManager.get_shared_file()
    if not shared_file:
        st.warning("⚠️ Пожалуйста, сначала загрузите файл во вкладке 'Информация о файле'")
        return

    # Проверка поддержки файла
    if not Config.is_image_like_file(shared_file["type"], shared_file["ext"]):
        show_unsupported_file_error(
            file_info=shared_file,
            supported_formats=list(Config.get_image_like_extensions()),
            operation_name="бинаризация"
        )
        return

    # --- ИСПОЛЬЗУЕМ FilePreviewComponent.render_file_info_and_page_selector ---
    # Обратите внимание: это для выбора страницы *исходного* файла перед обработкой
    selected_page_num_for_source = FilePreviewComponent.render_file_info_and_page_selector(
        shared_file, session_state_key_prefix="binary_source"
    )
    # --- /ИСПОЛЬЗУЕМ ---

    # --- ИСПОЛЬЗУЕМ SettingsPanel.render_binary_settings ---
    threshold_value = SettingsPanel.render_binary_settings()
    # --- /ИСПОЛЬЗУЕМ ---

    # Кнопка конвертации
    if st.button(f"🔄 Конвертировать с порогом {threshold_value}", type="primary"):
        _process_conversion(shared_file, threshold_value, selected_page_num_for_source) # Передаём page_num

    # Отображение результатов
    _display_results(shared_file["name"])


def _process_conversion(shared_file: dict, threshold_value: int, page_num: int): # Принимаем page_num
    """Обработка конвертации файла"""
    api_client = APIClient()

    with st.spinner(f"🔄 Конвертация с порогом {threshold_value}..."):
        try:
            # --- ПЕРЕДАЁМ page_num в API клиент ---
            # Предполагаем, что API и его клиент теперь принимают page_num
            result = api_client.convert_to_binary(
                file_data=shared_file["bytes"],
                filename=shared_file["name"],
                threshold=threshold_value,
                page_num=page_num
            )
            # --- /ПЕРЕДАЁМ ---

            # Сохранение результатов в сессию
            # Предполагаем, что API теперь возвращает один результат для одной страницы
            image_b64 = result.get("image_base64") # Изменим структуру ответа
            if not image_b64:
                st.error("Пустой результат от сервера.")
                return

            binary_image = base64.b64decode(image_b64)
            # Сохраняем один результат и номер страницы
            SessionManager.set_binary_results([binary_image], threshold_value, shared_file["name"], selected_page_num_for_source)

            st.success(f"✅ Конвертация выполнена успешно! (страница {page_num + 1})")

        except Exception as e:
            handle_api_error(e)


def _display_results(original_filename: str):
    """Отображение результатов конвертации"""
    binary_results = SessionManager.get_binary_results()
    if not binary_results:
        st.info("👆 Нажмите кнопку 'Конвертировать' для запуска обработки")
        return

    images = binary_results["images"]
    threshold = binary_results["threshold"]

    if not images:
        st.warning("Результат обработки пуст.")
        return

    # Берём первую (и единственную) страницу результата
    img_data = images[0]

    # Отображение результата
    _render_result_page(img_data, threshold, original_filename)


def _render_result_page(img_bytes, threshold: int, original_filename: str):
    """Отображение результата бинаризации одной страницы."""

    # ВВОД КОНСТАНТЫ ИМЕЕТ СМЫСЛ, потому что значение используется в нескольких местах.
    # Если логика изменится (хотя и маловероятно для этого сценария), нужно изменить только здесь.
    RESULT_PAGE_NUM_FOR_THIS_VIEW = 0

    # ВВОД КОНСТАНТЫ НЕ ИМЕЕТ СМЫСЛА, потому что она не используется в теле функции.
    # RESULT_PAGE_COUNT = 1

    # Используем RESULT_PAGE_NUM_FOR_THIS_VIEW
    page_title = f"Бинарное изображение (страница {RESULT_PAGE_NUM_FOR_THIS_VIEW + 1}, порог={threshold})"

    # Использование компонента предпросмотра
    FilePreviewComponent.render(
        file_bytes=img_data,
        file_type="image/png",
        file_name=f"binary_result_{original_filename}.png",
        file_ext=".png",
        title=page_title,
        show_metadata=False
    )

    output_filename = f"binary_{original_filename}_page_{RESULT_PAGE_NUM_FOR_THIS_VIEW + 1}_threshold_{threshold}.png"

    # Используем RESULT_PAGE_NUM_FOR_THIS_VIEW снова
    show_download_button(
        data=img_data,
        file_name=output_filename,
        mime_type="image/png",
        label="📥 Скачать бинарное изображение",
        key=f"download_binary_result_{RESULT_PAGE_NUM_FOR_THIS_VIEW}"  # <-- Вот здесь
)