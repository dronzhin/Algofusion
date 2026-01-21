import streamlit as st
import requests
import base64
from io import BytesIO
from PIL import Image
import cv2
import numpy as np
import fitz  # PyMuPDF для PDF
import io
from pathlib import Path


def _convert_to_image(file_bytes, file_type, file_ext, page_num=0):
    """
    Конвертирует файл в изображение в зависимости от типа

    Args:
        file_bytes: байты файла
        file_type: MIME-тип файла
        file_ext: расширение файла
        page_num: номер страницы для PDF (0-based)

    Returns:
        Байты изображения в формате PNG или None если конвертация невозможна
    """
    try:
        # Обработка PDF
        if file_type == "application/pdf" or file_ext == ".pdf":
            try:
                pdf_doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
                if page_num >= pdf_doc.page_count:
                    page_num = 0

                page = pdf_doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                pdf_doc.close()
                return img_data
            except Exception as e:
                st.warning(f"Ошибка конвертации PDF в изображение: {e}")
                return None

        # Обработка изображений
        elif file_type.startswith("image/") or file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
            try:
                # Проверяем, что это валидное изображение
                img = Image.open(BytesIO(file_bytes))
                img.load()  # Проверяем целостность

                # Конвертируем в RGB если нужно
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Сохраняем в PNG для единообразия
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
            except Exception as e:
                st.warning(f"Ошибка обработки изображения: {e}")
                return None

        # ЯВНО ИСКЛЮЧАЕМ НЕПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ
        else:
            st.warning(f"Формат файла {file_ext} не поддерживается для выравнивания")
            return None

    except Exception as e:
        st.error(f"Ошибка конвертации файла в изображение: {e}")
        return None


def render_image_rotation():
    """
    Streamlit интерфейс для выравнивания изображения по горизонтальной линии
    Работает только с оригинальным изображением из вкладки "Информация о файле"
    """
    st.subheader("📊 Выравнивание изображения по горизонтальной линии")
    st.markdown("""
    Этот инструмент найдет самую длинную горизонтальную линию на изображении,
    определит ее угол наклона и автоматически выровняет изображение.

    **Обработка выполняется на сервере** для максимальной производительности.

    **Поддерживаются только:** PDF, JPG, PNG, BMP, GIF
    """)

    # Проверяем наличие данных в session_state
    if "shared_file" not in st.session_state or st.session_state["shared_file"] is None:
        st.warning("⚠️ Сначала загрузите файл во вкладке 'Информация о файле'")
        st.stop()

    shared_file = st.session_state["shared_file"]
    file_ext = shared_file["ext"].lower()
    file_type = shared_file["type"]
    file_name = shared_file["name"]

    # Проверяем, поддерживается ли формат для выравнивания
    SUPPORTED_EXTS = [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".gif"]
    SUPPORTED_TYPES = ["application/pdf", "image/jpeg", "image/jpg", "image/png", "image/bmp", "image/gif"]

    is_supported_format = (
            file_ext in SUPPORTED_EXTS or
            any(file_type.startswith(supported) for supported in ["image/", "application/pdf"])
    )

    if not is_supported_format:
        st.error(f"❌ Формат файла '{file_ext}' не поддерживается для выравнивания")
        st.info("Поддерживаются только: PDF, JPG, JPEG, PNG, BMP, GIF")
        st.stop()

    # Показываем информацию о файле
    st.info(f"📄 Работаем с файлом: **{file_name}**")

    # Выбор страницы для PDF
    page_num = 0
    if file_ext == ".pdf":
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
                    key="pdf_page_selector"
                ) - 1  # 0-based индексация
            else:
                st.info("📄 PDF содержит одну страницу")
        except Exception as e:
            st.error(f"Ошибка при чтении PDF: {e}")
            st.stop()

    # Конвертируем файл в изображение
    with st.spinner(f"🔄 Подготовка изображения для обработки..."):
        image_bytes = _convert_to_image(shared_file["bytes"], file_type, file_ext, page_num)

    if image_bytes is None:
        st.error(f"❌ Не удалось подготовить изображение из файла {file_name}")
        st.info("Попробуйте другой файл или проверьте его целостность")
        st.stop()

    # Настройки обработки
    with st.expander("⚙️ Настройки детекции линий", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_line_length = st.slider(
                "Минимальная длина линии (пиксели)",
                min_value=10,
                max_value=500,
                value=50,
                step=10,
                key="min_line_length_server"
            )
        with col2:
            max_line_gap = st.slider(
                "Максимальный разрыв в линии (пиксели)",
                min_value=1,
                max_value=100,
                value=20,
                step=1,
                key="max_line_gap_server"
            )

        # Морфологические операции для улучшения качества
        use_morphology = st.checkbox(
            "Применить морфологические операции для улучшения линий",
            value=True,
            key="use_morphology_server"
        )
        st.info("Морфологические операции помогают соединить разорванные линии и удалить шум")

    # Показываем исходное изображение
    st.markdown("### 📷 Исходное изображение для выравнивания")
    try:
        display_image = Image.open(BytesIO(image_bytes))
        st.image(display_image, caption="Исходное изображение", width=800)
    except Exception as e:
        st.error(f"❌ Ошибка при отображении изображения: {e}")
        st.stop()

    # Кнопка обработки
    if st.button("🔄 Выровнять изображение на сервере", type="primary"):
        with st.spinner("🔍 Поиск горизонтальной линии и выравнивание изображения на сервере..."):
            try:
                # Подготавливаем файл для отправки
                files = {
                    "file": (file_name, image_bytes, "image/png")
                }

                # Подготавливаем параметры
                data = {
                    "min_line_length": str(min_line_length),
                    "max_line_gap": str(max_line_gap),
                    "use_morphology": "true" if use_morphology else "false"
                }

                # Отправляем запрос на сервер
                response = requests.post(
                    "http://localhost:8000/rotate",
                    files=files,
                    data=data,
                    timeout=60
                )

                # Обрабатываем ответ
                if response.status_code == 200:
                    result = response.json()

                    if result.get("success", False):
                        rotated_b64 = result.get("rotated_image_base64")
                        rotation_angle = result.get("rotation_angle", 0.0)
                        line_info = result.get("line_info")

                        if rotated_b64:
                            # Декодируем изображение
                            rotated_bytes = base64.b64decode(rotated_b64)
                            rotated_image = Image.open(BytesIO(rotated_bytes))

                            # Отображаем результат
                            st.markdown(f"### 🎯 Результат выравнивания (угол: {rotation_angle:.2f}°)")

                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**Исходное изображение**")
                                st.image(display_image, width=600)

                            with col2:
                                st.markdown("**Выровненное изображение**")
                                st.image(rotated_image, width=600)

                            # Информация о найденной линии
                            if line_info:
                                st.success(f"✅ Найдена горизонтальная линия длиной {line_info['length']:.1f} пикселей")
                                st.markdown(f"""
                                **Детали детекции:**
                                - Угол исходной линии: {line_info['detected_angle']:.2f}°
                                - Угол поворота: {rotation_angle:.2f}°
                                - Координаты линии: ({line_info['start'][0]}, {line_info['start'][1]}) → ({line_info['end'][0]}, {line_info['end'][1]})
                                """)

                                # Визуализация линии на исходном изображении
                                if st.checkbox("Показать найденную линию на исходном изображении",
                                               key="show_line_server"):
                                    try:
                                        # Конвертируем PIL Image в numpy array для OpenCV
                                        img_array = np.array(display_image)

                                        # Если изображение grayscale, конвертируем в RGB
                                        if len(img_array.shape) == 2:
                                            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
                                        elif img_array.shape[2] == 4:  # RGBA
                                            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

                                        # Рисуем линию
                                        cv2.line(img_array,
                                                 (int(line_info['start'][0]), int(line_info['start'][1])),
                                                 (int(line_info['end'][0]), int(line_info['end'][1])),
                                                 (0, 0, 255), 3)  # Красная линия

                                        # Конвертируем обратно в PIL Image
                                        img_with_line = Image.fromarray(img_array)
                                        st.image(img_with_line, caption="Исходное изображение с найденной линией",
                                                 width=800)
                                    except Exception as vis_error:
                                        st.warning(f"Не удалось отобразить линию: {vis_error}")
                            else:
                                st.info("ℹ️ Горизонтальные линии не найдены, изображение осталось без изменений")

                            # Кнопка скачивания
                            st.markdown("---")
                            rotated_bytes_io = BytesIO()
                            rotated_image.save(rotated_bytes_io, format='PNG')
                            rotated_bytes_io.seek(0)

                            output_filename = f"aligned_{Path(file_name).stem}_{rotation_angle:.1f}deg.png"

                            st.download_button(
                                label="📥 Скачать выровненное изображение",
                                data=rotated_bytes_io,
                                file_name=output_filename,
                                mime="image/png",
                                key="download_rotated_server"
                            )
                        else:
                            st.error("Ошибка: сервер не вернул изображение")
                    else:
                        error_msg = result.get("error", "Неизвестная ошибка сервера")
                        st.error(f"❌ Ошибка сервера: {error_msg}")
                else:
                    st.error(f"❌ Ошибка HTTP: {response.status_code}")
                    st.text("Тело ответа:")
                    st.text(response.text[:1000])

            except requests.exceptions.ConnectionError:
                st.error(
                    "⚠️ Не удаётся подключиться к серверу. Убедитесь, что FastAPI запущен на http://localhost:8000")
            except requests.exceptions.Timeout:
                st.error("⏰ Превышено время ожидания ответа от сервера (60 сек). Попробуйте уменьшить размер файла.")
            except Exception as e:
                st.exception(f"Непредвиденная ошибка: {e}")