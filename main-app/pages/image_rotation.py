import streamlit as st
from services.api_client import APIClient
from components.file_preview import FilePreviewComponent
from components.settings_panel import SettingsPanel
from utils import handle_api_error, handle_file_error, handle_image_processing_error, convert_file_to_image, \
    get_file_icon
from state.session_manager import SessionManager
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
import fitz  # PyMuPDF для PDF
from pathlib import Path


def render_page():
    """
    Страница выравнивания изображений с использованием SessionManager
    """
    st.subheader("📊 Выравнивание изображения по горизонтальной линии")
    st.markdown("""
    Этот инструмент найдет самую длинную горизонтальную линию на изображении,
    определит ее угол наклона и автоматически выровняет изображение.

    **Обработка выполняется на сервере** для максимальной производительности.

    **Поддерживаются только:** PDF, JPG, PNG, BMP, GIF
    """)

    # Инициализация сессии при первом запуске
    if "session_initialized" not in st.session_state:
        SessionManager.initialize_session()
        st.session_state["session_initialized"] = True

    # Проверка наличия файла
    shared_file = SessionManager.get_shared_file()
    if not shared_file:
        st.warning("⚠️ Сначала загрузите файл во вкладке 'Информация о файле'")
        # Очищаем результаты при отсутствии файла
        SessionManager.clear_rotation_results()
        SessionManager.set_show_line_state(False)
        return

    # Проверка поддержки формата
    if not _is_supported_for_rotation(shared_file):
        _show_unsupported_format_error(shared_file)
        SessionManager.clear_rotation_results()
        SessionManager.set_show_line_state(False)
        return

    # Отображение информации о файле
    _show_file_info(shared_file)

    # Подготовка изображения для обработки
    image_bytes = _prepare_image_for_rotation(shared_file)
    if not image_bytes:
        SessionManager.clear_rotation_results()
        SessionManager.set_show_line_state(False)
        return

    # Настройки обработки
    rotation_params = SettingsPanel.render_rotation_settings()

    # Кнопка обработки
    if st.button("🔄 Выровнять изображение на сервере", type="primary", key="rotate_button"):
        _process_rotation(shared_file, image_bytes, rotation_params)

    # Отображение результатов (если они есть)
    _display_results_if_available(shared_file["name"])


def _is_supported_for_rotation(shared_file: dict) -> bool:
    """
    Проверить, поддерживается ли файл для выравнивания
    """
    supported_types = [
        "application/pdf",
        "image/jpeg", "image/jpg", "image/png",
        "image/bmp", "image/gif"
    ]
    supported_exts = [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".gif"]

    return (shared_file["type"] in supported_types or
            shared_file["ext"].lower() in supported_exts)


def _show_unsupported_format_error(shared_file: dict):
    """
    Показать ошибку для неподдерживаемого формата
    """
    st.error(f"❌ Формат файла '{shared_file['ext']}' не поддерживается для выравнивания")
    st.info("Поддерживаются только: PDF, JPG, JPEG, PNG, BMP, GIF")
    st.markdown(f"""
    **Текущий файл:** {shared_file['name']}
    **Тип:** {shared_file['type']}
    **Расширение:** {shared_file['ext']}
    """)


def _show_file_info(shared_file: dict):
    """
    Отображение информации о файле
    """
    icon = get_file_icon(shared_file["type"], shared_file["ext"])
    st.info(f"{icon} Работаем с файлом: **{shared_file['name']}**")

    # Выбор страницы для PDF
    if shared_file["type"] == "application/pdf" or shared_file["ext"].lower() == ".pdf":
        _show_pdf_page_selector(shared_file)


def _show_pdf_page_selector(shared_file: dict):
    """
    Показать селектор страницы для PDF
    """
    try:
        pdf_doc = fitz.open(stream=BytesIO(shared_file["bytes"]), filetype="pdf")
        page_count = pdf_doc.page_count
        pdf_doc.close()

        if page_count > 1:
            page_num = st.number_input(
                "Выберите страницу для выравнивания:",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                key="pdf_page_selector_rotation"
            )
            st.session_state["rotation_page_num"] = page_num - 1
        else:
            st.info("📄 PDF содержит одну страницу")
            st.session_state["rotation_page_num"] = 0

    except Exception as e:
        handle_file_error(e, "PDF документ")


def _prepare_image_for_rotation(shared_file: dict) -> bytes:
    """
    Подготовка изображения для выравнивания
    """
    with st.spinner("🔄 Подготовка изображения для обработки..."):
        try:
            page_num = st.session_state.get("rotation_page_num", 0)

            image_bytes = convert_file_to_image(
                file_bytes=shared_file["bytes"],
                file_type=shared_file["type"],
                file_ext=shared_file["ext"],
                page_num=page_num
            )

            if not image_bytes:
                st.error("❌ Не удалось подготовить изображение для обработки")
                return None

            # Проверка размера изображения
            if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
                st.warning("⚠️ Изображение слишком большое для обработки. Попробуйте уменьшить размер.")

            return image_bytes

        except Exception as e:
            handle_image_processing_error(e, "подготовка изображения")
            return None


def _process_rotation(shared_file: dict, image_bytes: bytes, params: dict):
    """
    Обработка выравнивания изображения с использованием SessionManager
    """
    api_client = APIClient()

    with st.spinner("🔍 Поиск горизонтальной линии и выравнивание изображения на сервере..."):
        try:
            # Отправка запроса
            result = api_client.rotate_image(
                image_data=image_bytes,
                filename=shared_file["name"],
                params=params
            )

            if not result.get("success", False):
                error_msg = result.get("error", "Неизвестная ошибка сервера")
                handle_api_error(Exception(error_msg), "выравнивание изображения")
                SessionManager.clear_rotation_results()
                return

            # Сохраняем результаты через SessionManager
            rotation_results = {
                "original_image_bytes": image_bytes,
                "rotated_bytes": base64.b64decode(result.get("rotated_image_base64", "")),
                "rotation_angle": result.get("rotation_angle", 0.0),
                "line_info": result.get("line_info"),
                "original_filename": shared_file["name"],
                "params": params
            }

            SessionManager.set_rotation_results(rotation_results)
            st.success(f"✅ Выравнивание выполнено успешно! Угол поворота: {result.get('rotation_angle', 0.0):.2f}°")

        except Exception as e:
            handle_api_error(e, "выравнивание изображения")
            SessionManager.clear_rotation_results()


def _display_results_if_available(original_filename: str):
    """
    Отображение результатов с использованием SessionManager
    """
    rotation_results = SessionManager.get_rotation_results()

    if not rotation_results:
        st.info("👆 Нажмите кнопку 'Выровнять изображение на сервере' для запуска обработки")
        return

    original_image_bytes = rotation_results["original_image_bytes"]
    rotated_bytes = rotation_results["rotated_bytes"]
    rotation_angle = rotation_results["rotation_angle"]
    line_info = rotation_results["line_info"]
    params = rotation_results.get("params", {})

    # Отображение результатов
    st.markdown(f"### 🎯 Результат выравнивания (угол: {rotation_angle:.2f}°)")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Исходное изображение**")
        try:
            original_img = Image.open(BytesIO(original_image_bytes))
            st.image(original_img, use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка отображения исходного изображения: {e}")

    with col2:
        st.markdown("**Выровненное изображение**")
        try:
            rotated_img = Image.open(BytesIO(rotated_bytes))
            st.image(rotated_img, use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка отображения выровненного изображения: {e}")

    # Информация о найденной линии
    if line_info:
        st.success(f"✅ Найдена горизонтальная линия длиной {line_info['length']:.1f} пикселей")
        _show_line_details(line_info, rotation_angle)

        # Визуализация линии - ИСПОЛЬЗУЕМ SessionManager ДЛЯ СОСТОЯНИЯ
        current_show_line = SessionManager.get_show_line_state()
        show_line = st.checkbox("Показать найденную линию на исходном изображении",
                                value=current_show_line,
                                key="show_line_checkbox")

        # Сохраняем состояние через SessionManager
        SessionManager.set_show_line_state(show_line)

        if show_line:
            _visualize_detected_line(original_image_bytes, line_info)
    else:
        st.info("ℹ️ Горизонтальные линии не найдены, изображение осталось без изменений")

    # Кнопка скачивания
    _show_download_button(rotated_bytes, original_filename, rotation_angle)


def _show_line_details(line_info: dict, rotation_angle: float):
    """
    Отображение деталей о найденной линии
    """
    with st.expander("📊 Детали детекции линии", expanded=True):
        st.markdown(f"""
        **Параметры детекции:**
        - Угол исходной линии: {line_info['detected_angle']:.2f}°
        - Угол поворота для выравнивания: {rotation_angle:.2f}°
        - Длина линии: {line_info['length']:.1f} пикселей
        - Координаты линии: 
          - Начало: ({line_info['start'][0]}, {line_info['start'][1]})
          - Конец: ({line_info['end'][0]}, {line_info['end'][1]})
        """)


def _visualize_detected_line(image_bytes: bytes, line_info: dict):
    """
    Визуализация найденной линии на исходном изображении
    """
    try:
        # Загрузка изображения
        img = Image.open(BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_array = np.array(img)

        # Рисование линии
        start_point = (int(line_info['start'][0]), int(line_info['start'][1]))
        end_point = (int(line_info['end'][0]), int(line_info['end'][1]))

        cv2.line(img_array, start_point, end_point, (0, 0, 255), 3)  # Красная линия

        # Отображение
        st.image(img_array, caption="Исходное изображение с найденной линией", use_container_width=True)

    except Exception as e:
        st.warning(f"Не удалось отобразить линию: {e}")


def _show_download_button(rotated_bytes: bytes, original_filename: str, rotation_angle: float):
    """
    Кнопка для скачивания результата
    """
    st.markdown("---")

    # Генерация имени файла
    file_stem = Path(original_filename).stem
    output_filename = f"aligned_{file_stem}_{rotation_angle:.1f}deg.png"

    st.download_button(
        label="📥 Скачать выровненное изображение",
        data=rotated_bytes,
        file_name=output_filename,
        mime="image/png",
        key="download_rotated_result"
    )