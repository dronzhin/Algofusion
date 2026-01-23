import streamlit as st
import fitz  # PyMuPDF
from docx import Document
from io import BytesIO
from PIL import Image


def render_file_preview(file_bytes, file_type, file_name, file_ext, title="Предпросмотр файла", show_metadata=True):
    """
    Универсальная функция для отображения предпросмотра файла.
    Поддерживает: изображения, PDF, DOCX и другие форматы.

    Параметры:
    - file_bytes: байты файла
    - file_type: MIME-тип файла
    - file_name: имя файла
    - file_ext: расширение файла
    - title: заголовок раздела
    - show_metadata: показывать ли метаданные
    """
    st.subheader(title)

    if show_metadata:
        st.write(f"**Имя файла:** `{file_name}`")
        st.write(f"**Тип:** `{file_type}`")
        st.write(f"**Расширение:** `{file_ext}`")

    # Обработка изображений
    if file_type.startswith("image/") or file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
        try:
            st.image(file_bytes, caption="Изображение", width='stretch')
        except Exception as e:
            st.error(f"Ошибка отображения изображения: {e}")

    # Обработка PDF
    elif file_type == "application/pdf" or file_ext == ".pdf":
        try:
            pdf_doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
            page_count = pdf_doc.page_count

            if page_count == 0:
                st.warning("PDF не содержит страниц.")
                pdf_doc.close()
                return

            # Выбор страницы
            page_num = st.number_input(
                "Номер страницы",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                key=f"pdf_page_{title}_{file_name}"
            ) - 1

            # Отображение страницы
            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            st.image(img_data, caption=f"Страница {page_num + 1} из {page_count}", width='stretch')

            pdf_doc.close()

        except Exception as e:
            st.error(f"Ошибка при открытии PDF: {e}")

    # Обработка DOCX
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_ext == ".docx":
        try:
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]

            if not paragraphs:
                st.info("Документ пуст.")
                return

            # Настройки "страницы"
            PARAGRAPHS_PER_PAGE = 30
            total_pages = (len(paragraphs) + PARAGRAPHS_PER_PAGE - 1) // PARAGRAPHS_PER_PAGE

            page_num = st.number_input(
                "Страница (по параграфам)",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                key=f"docx_page_{title}_{file_name}"
            )

            start_idx = (page_num - 1) * PARAGRAPHS_PER_PAGE
            end_idx = start_idx + PARAGRAPHS_PER_PAGE
            page_paragraphs = paragraphs[start_idx:end_idx]

            st.markdown("### Содержимое:")
            for i, para in enumerate(page_paragraphs, start=start_idx + 1):
                st.markdown(f"{para}")

            st.caption(f"Параграфы {start_idx + 1}–{min(end_idx, len(paragraphs))} из {len(paragraphs)}")

        except Exception as e:
            st.error(f"Ошибка при чтении DOCX: {e}")

    # Обработка других типов
    else:
        st.info("Предпросмотр недоступен для этого типа файла.")
        if isinstance(file_bytes, bytes) and len(file_bytes) < 10000:  # небольшие текстовые файлы
            try:
                text_content = file_bytes.decode('utf-8')
                st.text_area("Содержимое файла", text_content, height=300)
            except:
                pass