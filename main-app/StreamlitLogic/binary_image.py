import streamlit as st
import requests
import base64
from StreamlitLogic.file_renderer import render_file_preview


def render_binary_image():
    """
    Функция для отображения интерфейса конвертации в чёрно-белое изображение.
    Использует файл, загруженный в первой вкладке.
    Содержит поле для ввода порога бинаризации прямо в этой вкладке.
    """
    st.subheader("🖨️ Конвертер в чёрно-белое (бинарное) изображение")
    st.markdown("Использует файл, загруженный во вкладке 'Информация о файле'.")

    # Проверяем, есть ли файл в состоянии
    if "shared_file" not in st.session_state or st.session_state["shared_file"] is None:
        st.warning("⚠️ Пожалуйста, сначала загрузите файл во вкладке 'Информация о файле'")
        st.stop()

    shared_file = st.session_state["shared_file"]
    file_bytes = shared_file["bytes"]
    file_type = shared_file["type"]
    file_name = shared_file["name"]
    file_ext = shared_file["ext"]

    st.info(f"📄 Используется файл: **{file_name}**")

    # === Настройки конвертации ===
    st.markdown("### ⚙️ Настройки бинаризации")

    # Поле для ввода порога
    col1, col2 = st.columns([2, 1])

    with col1:
        threshold_value = st.number_input(
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

    # Проверяем, поддерживается ли файл для конвертации
    SUPPORTED_TYPES = [
        "image/jpeg", "image/jpg", "image/png",
        "application/pdf"
    ]
    SUPPORTED_EXTS = [".jpg", ".jpeg", ".png", ".pdf"]

    is_supported = (
            file_type in SUPPORTED_TYPES or
            file_ext in SUPPORTED_EXTS
    )

    if not is_supported:
        st.error("❌ Конвертация в бинарный формат невозможна для этого типа файла.")
        st.info("Поддерживаются только PDF, JPG и PNG файлы.")
        st.stop()

    # === Кнопка для конвертации ===
    st.markdown("---")
    if st.button("🔄 Конвертировать с порогом " + str(threshold_value), key="convert_btn", type="primary"):
        with st.spinner(f"🔄 Конвертация с порогом {threshold_value}..."):
            try:
                # Правильный способ отправки multipart/form-data с параметрами
                files = {
                    "file": (file_name, file_bytes, file_type),
                    "threshold": (None, str(threshold_value)),  # Параметр как часть формы
                    "output_format": (None, "base64")
                }

                response = requests.post("http://localhost:8000/convert", files=files, timeout=30)

                # Отладочная информация
                with st.expander("🔍 Отладочная информация", expanded=False):
                    st.write(f"**Отправленный порог:** {threshold_value}")
                    st.write(f"**Статус ответа:** {response.status_code}")
                    st.write(f"**Content-Type:** {response.headers.get('content-type', '')}")
                    if response.status_code != 200:
                        st.write("**Тело ответа:**")
                        st.text(response.text[:500])

                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        result = response.json()
                        images_b64 = result.get("images_base64", [])
                        if not images_b64:
                            st.error("Пустой результат от сервера.")
                            st.stop()

                        # Сохраняем результаты в состояние
                        st.session_state["binary_images"] = []
                        for i, b64_str in enumerate(images_b64):
                            img_data = base64.b64decode(b64_str)
                            st.session_state["binary_images"].append(img_data)

                        # Сохраняем текущие параметры
                        st.session_state["current_threshold"] = threshold_value
                        st.session_state["current_binary_file"] = file_name

                        st.success(f"✅ Конвертация выполнена успешно!")
                    else:
                        st.error("Сервер вернул не JSON. Возможно, ошибка.")
                        st.text(response.text[:1000])
                        st.stop()
                else:
                    st.error(f"❌ Ошибка сервера: {response.status_code}")
                    st.text(response.text[:1000])
                    st.stop()

            except requests.exceptions.ConnectionError:
                st.error(
                    "⚠️ Не удаётся подключиться к серверу. Убедитесь, что FastAPI запущен на http://localhost:8000")
                st.stop()
            except requests.exceptions.Timeout:
                st.error("⏰ Превышено время ожидания ответа от сервера (30 сек). Попробуйте уменьшить размер файла.")
                st.stop()
            except Exception as e:
                st.exception(f"Непредвиденная ошибка: {e}")
                st.stop()

    # === Отображение результатов ===
    if "binary_images" in st.session_state and st.session_state["binary_images"]:
        binary_images = st.session_state["binary_images"]
        page_count = len(binary_images)
        current_threshold = st.session_state.get("current_threshold", threshold_value)

        # Выбор страницы для отображения
        if page_count > 1:
            page_num = st.number_input(
                "Номер страницы",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                key="binary_page_selector"
            ) - 1  # 0-based индексация
        else:
            page_num = 0
            st.info("📄 Результат содержит одну страницу")

        # Отображаем выбранную страницу
        if 0 <= page_num < page_count:
            img_data = binary_images[page_num]

            # Создаем временный файл в памяти для рендеринга
            page_title = f"Страница {page_num + 1} из {page_count} (порог={current_threshold})"
            render_file_preview(
                file_bytes=img_data,
                file_type="image/png",
                file_name=f"page_{page_num + 1}_binary.png",
                file_ext=".png",
                title=page_title,
                show_metadata=False
            )

            # Добавляем возможность скачать результат
            st.download_button(
                label="📥 Скачать эту страницу",
                data=img_data,
                file_name=f"binary_page_{page_num + 1}_threshold_{current_threshold}.png",
                mime="image/png",
                key=f"download_page_{page_num}"
            )
        else:
            st.error("Неверный номер страницы")
    else:
        st.info("👆 Нажмите кнопку 'Конвертировать' для запуска обработки")
