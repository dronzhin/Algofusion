import streamlit as st
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document

def _handle_image(uploaded_file):
    """Обработка изображений: JPG, PNG"""
    st.image(uploaded_file, caption="Предпросмотр изображения", width='stretch')


def _handle_pdf(uploaded_file):
    """Обработка PDF-файлов с постраничной навигацией"""
    import io

    try:
        pdf_bytes = uploaded_file.getvalue()
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        page_count = doc.page_count

        if page_count == 0:
            st.warning("PDF не содержит страниц.")
            doc.close()
            return

        # Выбор страницы: можно использовать selectbox или slider
        page_num = st.number_input(
            "Номер страницы",
            min_value=1,
            max_value=page_count,
            value=1,
            step=1
        ) - 1  # fitz использует 0-based индексацию

        # Отображаем выбранную страницу
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        st.image(img_data, caption=f"Страница {page_num + 1} из {page_count}", width='stretch')

        doc.close()

    except Exception as e:
        st.error(f"Ошибка при открытии PDF: {e}")


def _handle_docx(uploaded_file):
    """Обработка DOCX-файлов с постраничным просмотром по параграфам"""
    import io
    try:
        docx_bytes = uploaded_file.getvalue()
        doc = Document(io.BytesIO(docx_bytes))
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
            step=1
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


def _handle_other():
    """Обработка неподдерживаемых типов"""
    st.info("Файл не поддерживается для предпросмотра. Доступны только метаданные.")


def render_file_info():
    """
    Основная точка входа.
    Загружает файл и делегирует обработку в зависимости от типа.
    """
    st.subheader("📄 Анализ файла")
    uploaded = st.file_uploader("Загрузите файл", key="file_info_uploader")

    if uploaded is None:
        return

    file_name = uploaded.name
    file_size = uploaded.size
    mime_type = uploaded.type
    file_ext = Path(file_name).suffix.lower()

    # Вывод метаданных
    st.write(f"**Имя файла:** `{file_name}`")
    st.write(f"**Размер:** {file_size} байт ({file_size / 1024:.2f} КБ)")
    st.write(f"**MIME-тип:** `{mime_type}`")
    st.write(f"**Расширение:** `{file_ext}`")

    # Маршрутизация по типу
    if mime_type in ["image/jpeg", "image/jpg", "image/png"] or file_ext in [".jpg", ".jpeg", ".png"]:
        _handle_image(uploaded)
    elif mime_type == "application/pdf" or file_ext == ".pdf":
        _handle_pdf(uploaded)
    elif (
        mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or file_ext == ".docx"
    ):
        _handle_docx(uploaded)
    else:
        _handle_other()