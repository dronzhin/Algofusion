import streamlit as st
import fitz
from docx import Document
from io import BytesIO
from utils import is_image_file, is_pdf_file, is_docx_file


class FilePreviewComponent:
    """
    Компонент для предпросмотра файлов
    Следует принципу единственной ответственности
    """

    @staticmethod
    def render(file_bytes: bytes, file_type: str, file_name: str, file_ext: str,
               title: str = "Предпросмотр файла", show_metadata: bool = True):
        """Основной метод рендеринга"""
        st.subheader(title)

        if show_metadata:
            FilePreviewComponent._show_metadata(file_name, file_type, file_ext)

        if is_image_file(file_type, file_ext):
            FilePreviewComponent._render_image(file_bytes)
        elif is_pdf_file(file_type, file_ext):
            FilePreviewComponent._render_pdf(file_bytes, file_name)
        elif is_docx_file(file_type, file_ext):
            FilePreviewComponent._render_docx(file_bytes, file_name)
        else:
            FilePreviewComponent._render_generic(file_bytes, file_ext)

    @staticmethod
    def _show_metadata(file_name: str, file_type: str, file_ext: str):
        st.write(f"**Имя файла:** `{file_name}`")
        st.write(f"**Тип:** `{file_type}`")
        st.write(f"**Расширение:** `{file_ext}`")

    @staticmethod
    def _render_image(file_bytes: bytes):
        try:
            st.image(file_bytes, caption="Изображение", use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка отображения изображения: {e}")

    @staticmethod
    def _render_pdf(file_bytes: bytes, file_name: str):
        try:
            pdf_doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
            page_count = pdf_doc.page_count

            if page_count == 0:
                st.warning("PDF не содержит страниц.")
                pdf_doc.close()
                return

            page_num = st.number_input(
                "Номер страницы",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                key=f"pdf_page_{file_name}"
            ) - 1

            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            img_data = pix.tobytes("png")
            st.image(img_data, caption=f"Страница {page_num + 1} из {page_count}", use_container_width=True)

            pdf_doc.close()
        except Exception as e:
            st.error(f"Ошибка при открытии PDF: {e}")

    @staticmethod
    def _render_docx(file_bytes: bytes, file_name: str):
        try:
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]

            if not paragraphs:
                st.info("Документ пуст.")
                return

            PARAGRAPHS_PER_PAGE = 30
            total_pages = (len(paragraphs) + PARAGRAPHS_PER_PAGE - 1) // PARAGRAPHS_PER_PAGE

            page_num = st.number_input(
                "Страница (по параграфам)",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                key=f"docx_page_{file_name}"
            )

            start_idx = (page_num - 1) * PARAGRAPHS_PER_PAGE
            end_idx = start_idx + PARAGRAPHS_PER_PAGE
            page_paragraphs = paragraphs[start_idx:end_idx]

            st.markdown("### Содержимое:")
            for para in page_paragraphs:
                st.markdown(f"{para}")

            st.caption(f"Параграфы {start_idx + 1}–{min(end_idx, len(paragraphs))} из {len(paragraphs)}")
        except Exception as e:
            st.error(f"Ошибка при чтении DOCX: {e}")

    @staticmethod
    def _render_generic(file_bytes: bytes, file_ext: str):
        st.info("Предпросмотр недоступен для этого типа файла.")
        if isinstance(file_bytes, bytes) and len(file_bytes) < 10000:
            try:
                text_content = file_bytes.decode('utf-8')
                st.text_area("Содержимое файла", text_content, height=300)
            except:
                pass