import streamlit as st
import requests
import base64
from io import BytesIO
from PIL import Image, ImageOps
import cv2
import numpy as np
import fitz  # PyMuPDF для PDF
from docx import Document
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

        # Обработка DOCX
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_ext == ".docx":
            try:
                # Для DOCX создаем "изображение" с текстом
                doc = Document(BytesIO(file_bytes))
                paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]

                if not paragraphs:
                    return None

                # Создаем изображение с текстом
                from PIL import ImageDraw, ImageFont

                # Создаем белое изображение
                img = Image.new('RGB', (800, 600), color='white')
                draw = ImageDraw.Draw(img)

                # Пытаемся найти шрифт
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", 14)
                except:
                    font = ImageFont.load_default()

                # Рисуем текст
                y_position = 20
                for para in paragraphs[:20]:  # берем первые 20 параграфов
                    draw.text((20, y_position), para[:80] + "..." if len(para) > 80 else para,
                              fill="black", font=font)
                    y_position += 25
                    if y_position > 550:
                        break

                # Конвертируем в байты
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
            except Exception as e:
                st.warning(f"Ошибка конвертации DOCX в изображение: {e}")
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

        # Другие типы файлов - не поддерживаем для выравнивания
        else:
            st.warning(f"Тип файла {file_type} не поддерживается для выравнивания")
            return None

    except Exception as e:
        st.error(f"Ошибка конвертации файла в изображение: {e}")
        return None


def render_image_rotation():
    """
    Streamlit интерфейс для выравнивания изображения по горизонтальной линии
    с обработкой на сервере
    """
    st.subheader("📊 Выравнивание изображения по горизонтальной линии")
    st.markdown("""
    Этот инструмент найдет самую длинную горизонтальную линию на изображении,
    определит ее угол наклона и автоматически выровняет изображение.

    **Обработка выполняется на сервере** для максимальной производительности.

    **Выберите тип изображения для обработки:**
    - **Оригинальное изображение** - исходное изображение из вкладки "Информация о файле"
    - **Бинарное изображение** - результат конвертации из вкладки "Бинарное изображение"

    **Поддерживаются:** PDF, JPG, PNG, документы (ограниченная поддержка)
    """)

    # Проверяем наличие данных в session_state
    has_original_file = "shared_file" in st.session_state and st.session_state["shared_file"] is not None
    has_binary_images = "binary_images" in st.session_state and st.session_state["binary_images"]

    if not has_original_file:
        st.warning("⚠️ Сначала загрузите файл во вкладке 'Информация о файле'")
        st.stop()

    # Выбор типа изображения
    image_type = st.radio(
        "Выберите тип изображения для выравнивания:",
        ["Оригинальное изображение", "Бинарное изображение"],
        key="image_type_selector_server",
        help="Бинарное изображение часто дает лучшие результаты для детекции линий"
    )

    # Получаем изображение в зависимости от выбора
    image_bytes = None
    image_source = ""
    current_threshold = None
    file_content_type = "image/png"
    is_binary_image = False
    file_name = ""
    file_ext = ""

    if image_type == "Оригинальное изображение":
        shared_file = st.session_state["shared_file"]
        original_bytes = shared_file["bytes"]
        image_source = shared_file["name"]
        file_content_type = shared_file["type"]
        file_name = shared_file["name"]
        file_ext = shared_file["ext"]
        image_type_for_display = "оригинальное"
        is_binary_image = False

        # Конвертируем файл в изображение
        with st.spinner(f"🔄 Конвертация {file_name} в изображение для обработки..."):
            image_bytes = _convert_to_image(original_bytes, file_content_type, file_ext)

        if image_bytes is None:
            st.error(f"❌ Не удалось конвертировать {file_name} в изображение для выравнивания")
            st.info("Поддерживаются только PDF, JPG, PNG и текстовые документы")
            st.stop()

        # Для оригинальных изображений используем имя файла как имя изображения
        display_file_name = f"{Path(file_name).stem}_page.png"

    else:  # Бинарное изображение
        if not has_binary_images:
            st.warning("⚠️ Сначала выполните конвертацию во вкладке 'Бинарное изображение'")
            st.stop()

        binary_images = st.session_state["binary_images"]
        current_threshold = st.session_state.get("current_threshold", 128)

        if len(binary_images) > 1:
            page_num = st.number_input(
                "Выберите страницу для выравнивания:",
                min_value=1,
                max_value=len(binary_images),
                value=1,
                step=1,
                key="binary_page_for_rotation_server"
            ) - 1
        else:
            page_num = 0
            st.info(f"📄 Используется единственная страница бинарного изображения (порог={current_threshold})")

        if 0 <= page_num < len(binary_images):
            # Получаем байты бинарного изображения
            image_bytes = binary_images[page_num]
            image_source = f"страница {page_num + 1} (бинарное, порог={current_threshold})"
            file_name = f"binary_page_{page_num + 1}.png"
            file_content_type = "image/png"
            image_type_for_display = "бинарное"
            is_binary_image = True
        else:
            st.error("Неверный номер страницы")
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

        # Дополнительные настройки для бинарных изображений
        use_morphology = False
        if image_type == "Бинарное изображение":
            st.markdown("### 🔧 Дополнительные настройки для бинарных изображений")
            use_morphology = st.checkbox(
                "Применить морфологические операции для улучшения линий",
                value=True,
                key="use_morphology_server"
            )
            st.info("Морфологические операции помогают соединить разорванные линии и удалить шум")

    # Показываем выбранное изображение
    st.markdown(f"### 📷 Выбранное изображение: {image_type_for_display.upper()}")
    st.info(f"Источник: {image_source}")

    try:
        # Отображаем изображение
        display_image = Image.open(BytesIO(image_bytes))
        st.image(display_image, caption=f"{image_type_for_display.capitalize()} изображение для обработки", width=800)

    except Exception as e:
        st.error(f"❌ Ошибка при отображении изображения: {e}")
        st.info("Попробуйте следующие решения:")
        st.markdown("""
        1. **Для PDF**: Убедитесь, что PDF содержит изображения или текст, который можно конвертировать
        2. **Для документов**: Попробуйте PDF или изображение вместо DOCX
        3. **Для всех типов**: Перезагрузите файл и повторите обработку
        """)

        # Показываем отладочную информацию
        with st.expander("🔧 Отладочная информация", expanded=False):
            st.write(f"Тип изображения: {image_type}")
            st.write(f"Размер данных: {len(image_bytes) if image_bytes else 0} байт")
            st.write(f"Content-Type: {file_content_type}")
            st.write(f"Имя файла: {file_name}")

        st.stop()

    # Кнопка обработки
    if st.button(f"🔄 Выровнять {image_type_for_display} изображение на сервере", type="primary"):
        with st.spinner(
                f"🔍 Поиск горизонтальной линии и выравнивание {image_type_for_display} изображения на сервере..."):
            try:
                # Подготавливаем файл для отправки
                files = {
                    "file": (file_name, image_bytes, file_content_type)
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
                            st.markdown(f"### 🎯 Результат выравнивания {image_type_for_display} изображения")

                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**Исходное изображение**")
                                st.image(display_image, width=600)

                            with col2:
                                st.markdown(f"**Выровненное изображение** (угол: {rotation_angle:.2f}°)")
                                st.image(rotated_image, width=600)

                            # Информация о найденной линии
                            if line_info:
                                st.success(f"✅ Найдена горизонтальная линия длиной {line_info['length']:.1f} пикселей")
                                st.markdown(f"""
                                **Детали детекции:**
                                - Тип изображения: {image_type_for_display}
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
                                st.info("ℹ️ Горизонтальные линии не найдены, но изображение было повернуто на 0°")

                            # Кнопка скачивания
                            st.markdown("---")
                            rotated_bytes_io = BytesIO()
                            rotated_image.save(rotated_bytes_io, format='PNG')
                            rotated_bytes_io.seek(0)

                            output_filename = f"aligned_{image_type_for_display.replace(' ', '_')}_{rotation_angle:.1f}deg.png"

                            st.download_button(
                                label=f"📥 Скачать выровненное {image_type_for_display} изображение",
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

    # Советы по использованию
    st.markdown("### 💡 Советы для разных типов файлов")
    st.markdown("""
    **Для PDF файлов:**
    - ✅ Работает с PDF, содержащими изображения и текст
    - ✅ Для сканов документов используйте бинарное изображение с порогом 120-150
    - ❌ Не работает с защищенными/зашифрованными PDF

    **Для изображений (JPG/PNG):**
    - ✅ Лучше всего работают изображения с четкими горизонтальными линиями
    - ✅ Для документов используйте порог 128 при бинаризации
    - ❌ Избегайте сильно сжатых JPG с артефактами

    **Для текстовых документов (DOCX):**
    - ⚠️ Ограниченная поддержка: генерируется изображение с текстом
    - ⚠️ Не рекомендуется для точного выравнивания
    - 💡 Лучше конвертировать DOCX в PDF или изображение заранее
    """)