# pages/binary_image.py
import streamlit as st
from services import APIClient
from components import FilePreviewComponent, SettingsPanel, show_unsupported_file_error, handle_api_error, \
    show_download_button, select_page_number_ui
from state import SessionManager
import base64
from config import Config
from utils import get_file_icon


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

    # Для отображения информации о файле, если нужно, можно вызвать:
    icon = get_file_icon(shared_file["type"], shared_file["ext"])
    st.info(f"{icon} Работаем с файлом: **{shared_file['name']}**")
    threshold_value = SettingsPanel.render_binary_settings()

    # Кнопка конвертации
    if st.button(f"🔄 Конвертировать с порогом {threshold_value}", type="primary"):
        # Убираем page_num из вызова, так как API его не принимает
        _process_conversion(shared_file, threshold_value) # Не передаём page_num

    # Отображение результатов
    _display_results(shared_file["name"])


def _process_conversion(shared_file: dict, threshold_value: int): # Убрали page_num
    """Обработка конвертации файла"""
    api_client = APIClient()

    with st.spinner(f"🔄 Конвертация с порогом {threshold_value}..."):
        try:
            # --- НЕ ПЕРЕДАЁМ page_num в API клиент ---
            # API обрабатывает весь файл
            result = api_client.convert_to_binary(
                file_data=shared_file["bytes"],
                filename=shared_file["name"],
                threshold=threshold_value,
                # page_num=page_num # <-- УБРАНО
            )
            # --- /НЕ ПЕРЕДАЁМ ---

            # Сохранение результатов в сессию (API возвращает список изображений)
            images_b64_list = result.get("images_base64", [])
            if not images_b64_list:
                st.error("Пустой результат от сервера.")
                return

            # Декодируем все строки base64
            binary_images = [base64.b64decode(b64_str) for b64_str in images_b64_list]
            # Сохраняем список изображений и параметры
            SessionManager.set_binary_results(binary_images, threshold_value, shared_file["name"])

            # Учитываем, что может быть несколько страниц
            page_count = len(binary_images)
            if page_count == 1:
                st.success(f"✅ Конвертация выполнена успешно!")
            else:
                st.success(f"✅ Конвертация выполнена успешно! Обработано {page_count} страниц.")


        except Exception as e:
            handle_api_error(e)


def _display_results(original_filename: str):
    """Отображение результатов конвертации"""
    binary_results = SessionManager.get_binary_results()
    if not binary_results:
        st.info("👆 Нажмите кнопку 'Конвертировать' для запуска обработки")
        return

    images = binary_results["images"] # Список байтов изображений
    threshold = binary_results["threshold"]

    if not images:
        st.warning("Результат обработки пуст.")
        return

    page_count = len(images)
    page_num = 0 # По умолчанию первая страница (0-indexed)

    if page_count > 1:
        # Используем общую функцию для выбора страницы результата
        from components.ui_helpers import select_page_number_ui
        # Ключ для session_state должен быть уникальным для этой страницы и операции
        selected_page_1_indexed = select_page_number_ui(
             page_count, min_value=1, max_value=page_count, initial_value=1, key_suffix="binary_result_display"
        )
        page_num = selected_page_1_indexed - 1 # Преобразуем в 0-indexed для доступа к списку
    else:
        st.info("📄 Результат содержит одну страницу")

    # Отображение выбранной страницы результата
    if 0 <= page_num < page_count:
        img_data = images[page_num]
        # Передаём page_num и page_count в функцию отображения
        _render_result_page(img_data, page_num, page_count, threshold, original_filename)
    else:
        st.error("Ошибка: выбранный номер страницы результата вне диапазона.")


def _render_result_page(img_bytes, page_num: int, page_count: int, threshold: int, original_filename: str):
    """Отображение результата бинаризации одной страницы."""

    # Используем переданный page_num (0-indexed) для отображения (преобразуем в 1-indexed)
    page_title = f"Бинарное изображение (страница {page_num + 1} из {page_count}, порог={threshold})"

    # Использование компонента предпросмотра
    FilePreviewComponent.render(
        file_bytes=img_bytes,
        file_type="image/png",
        file_name=f"binary_result_{original_filename}_page_{page_num + 1}.png",
        file_ext=".png",
        title=page_title,
        show_meta=False
    )

    output_filename = f"binary_{original_filename}_page_{page_num + 1}_threshold_{threshold}.png"

    # Используем переданный page_num снова для уникальности ключа
    show_download_button(
        data=img_bytes,
        file_name=output_filename,
        mime_type="image/png",
        label="📥 Скачать эту страницу",
        key=f"download_binary_result_page_{page_num}"  # <-- Вот здесь
    )
