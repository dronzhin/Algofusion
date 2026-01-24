# pages/binary_image.py
import streamlit as st
from services import APIClient
from components import FilePreviewComponent, show_unsupported_file_error, handle_api_error
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

    # Отображение информации о файле
    st.info(f"📄 Используется файл: **{shared_file['name']}**")

    # Настройки бинаризации
    threshold_value = _get_threshold_settings()

    # Кнопка конвертации
    if st.button(f"🔄 Конвертировать с порогом {threshold_value}", type="primary"):
        _process_conversion(shared_file, threshold_value)

    # Отображение результатов
    _display_results(shared_file["name"])

def _get_threshold_settings() -> int:
    """Получить настройки порога от пользователя"""
    col1, col2 = st.columns([2, 1])

    with col1:
        threshold = st.number_input(
            "Порог бинаризации (0-255)",
            min_value=0,
            max_value=255,
            value=128,
            step=1,
            help="Значение яркости: выше порога → белый, ниже → черный"
        )

    with col2:
        st.markdown("**Рекомендации:**")
        st.markdown("- Документы: 120-150")
        st.markdown("- Чертежи: 80-100")
        st.markdown("- Фото с текстом: 180-200")

    return threshold


def _process_conversion(shared_file: dict, threshold_value: int):
    """Обработка конвертации файла"""
    api_client = APIClient()

    with st.spinner(f"🔄 Конвертация с порогом {threshold_value}..."):
        try:
            result = api_client.convert_to_binary(
                file_data=shared_file["bytes"],
                filename=shared_file["name"],
                threshold=threshold_value
            )

            # Сохранение результатов в сессию
            images_b64 = result.get("images_base64", [])
            if not images_b64:
                st.error("Пустой результат от сервера.")
                return

            binary_images = [base64.b64decode(b64_str) for b64_str in images_b64]
            SessionManager.set_binary_results(binary_images, threshold_value, shared_file["name"])

            st.success(f"✅ Конвертация выполнена успешно!")

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
    page_count = len(images)

    # Выбор страницы
    page_num = _select_page_number(page_count)

    # Отображение выбранной страницы
    if 0 <= page_num < page_count:
        _render_result_page(images[page_num], page_num, page_count, threshold, original_filename)


def _select_page_number(page_count: int) -> int:
    """Выбор номера страницы для отображения"""
    if page_count > 1:
        return st.number_input(
            "Номер страницы",
            min_value=1,
            max_value=page_count,
            value=1,
            step=1,
            key="binary_page_selector"
        ) - 1
    else:
        st.info("📄 Результат содержит одну страницу")
        return 0


def _render_result_page(img_data: bytes, page_num: int, page_count: int,
                        threshold: int, original_filename: str):
    """Отображение результата для конкретной страницы"""
    page_title = f"Страница {page_num + 1} из {page_count} (порог={threshold})"

    # Использование компонента предпросмотра
    FilePreviewComponent.render(
        file_bytes=img_data,
        file_type="image/png",
        file_name=f"page_{page_num + 1}_binary.png",
        file_ext=".png",
        title=page_title,
        show_metadata=False
    )

    # Кнопка скачивания
    st.download_button(
        label="📥 Скачать эту страницу",
        data=img_data,
        file_name=f"binary_page_{page_num + 1}_threshold_{threshold}.png",
        mime="image/png",
        key=f"download_page_{page_num}"
    )