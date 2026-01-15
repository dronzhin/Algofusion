import streamlit as st
import requests
import base64
from io import BytesIO
from PIL import Image
from StreamlitLogic.file_renderer import render_file_preview


def render_binary_image():
    """
    Функция для отображения интерфейса конвертации в чёрно-белое изображение.
    Использует файл, загруженный в первой вкладке.
    Конвертирует только PDF и изображения, для остальных типов показывает сообщение.
    Результат отображается постранично с выбором номера страницы.
    Использует параметры из вкладки 'Параметры'.
    """
    st.subheader("🖨️ Конвертер в чёрно-белое (бинарное) изображение")
    st.markdown("Использует файл, загруженный во вкладке 'Информация о файле' и параметры из вкладки 'Параметры'.")

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

    # Показываем текущие параметры
    if "threshold" in st.session_state:
        st.markdown(f"⚙️ **Текущие параметры:** Порог = {st.session_state['threshold']}")
        if st.session_state.get("invert_colors"):
            st.markdown("🔄 **Цвета инвертированы**")

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

    # === Конвертация файла ===
    with st.spinner("🔄 Конвертация в чёрно-белый формат..."):
        files = {"file": (file_name, file_bytes, file_type)}

        # Используем параметры из session_state
        threshold_value = st.session_state.get("threshold", 128)
        data = {
            "output_format": "base64",
            "threshold": threshold_value
        }

        try:
            response = requests.post("http://localhost:8000/convert", files=files, data=data, timeout=30)

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    result = response.json()
                    images_b64 = result.get("images_base64", [])
                    if not images_b64:
                        st.error("Пустой результат от сервера.")
                        st.stop()

                    # Сохраняем сконвертированные изображения в состояние для постраничного просмотра
                    if "binary_images" not in st.session_state or st.session_state.get(
                            "current_binary_file") != file_name:
                        st.session_state["binary_images"] = []
                        for b64_str in images_b64:
                            img_data = base64.b64decode(b64_str)
                            st.session_state["binary_images"].append(img_data)
                        st.session_state["current_binary_file"] = file_name

                    binary_images = st.session_state["binary_images"]
                    page_count = len(binary_images)

                    st.subheader(f"📤 Итоговый результат (чёрно-белый, {page_count} стр.)")

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
                        page_title = f"Страница {page_num + 1} из {page_count} (чёрно-белая, порог={threshold_value})"
                        render_file_preview(
                            file_bytes=img_data,
                            file_type="image/png",
                            file_name=f"page_{page_num + 1}_binary.png",
                            file_ext=".png",
                            title=page_title,
                            show_metadata=False
                        )
                    else:
                        st.error("Неверный номер страницы")

                else:
                    st.error("Сервер вернул не JSON. Возможно, ошибка.")
                    st.text(response.text[:1000])
            else:
                st.error(f"Ошибка сервера: {response.status_code}")
                st.text(response.text[:1000])

        except requests.exceptions.ConnectionError:
            st.error("⚠️ Не удаётся подключиться к серверу. Убедитесь, что FastAPI запущен на http://localhost:8000")
        except requests.exceptions.Timeout:
            st.error("⏰ Превышено время ожидания ответа от сервера (30 сек). Попробуйте уменьшить размер файла.")
        except Exception as e:
            st.exception(f"Непредвиденная ошибка: {e}")