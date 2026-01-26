# components/file_preview.py
import streamlit as st
import fitz
from docx import Document
from io import BytesIO
import logging
from config import Config
from utils import get_file_icon

# Создаём логгер для этого модуля
logger = logging.getLogger(f"app.{__name__}")

class FilePreviewComponent:
    """
    Компонент для предпросмотра файлов
    Следует принципу единственной ответственности
    """

    @staticmethod
    def render(file_bytes: bytes, file_type: str, file_name: str, file_ext: str,
               title: str = "Предпросмотр файла", show_metadata: bool = True):
        """Основной метод рендеринга"""
        logger.debug(f"Начало рендеринга превью для файла: {file_name} ({file_type})")
        st.subheader(title)

        if show_metadata:
            FilePreviewComponent._show_metadata(file_name, file_type, file_ext)

        try:
            if Config.is_image_file(file_type, file_ext):
                logger.info(f"Рендеринг изображения: {file_name}")
                FilePreviewComponent._render_image(file_bytes)
            elif Config.is_pdf_file(file_type, file_ext):
                logger.info(f"Рендеринг PDF: {file_name}")
                FilePreviewComponent._render_pdf(file_bytes, file_name)
            elif Config.is_docx_file(file_type, file_ext):
                logger.info(f"Рендеринг DOCX: {file_name}")
                FilePreviewComponent._render_docx(file_bytes, file_name)
            else:
                logger.warning(f"Неподдерживаемый тип файла: {file_name} ({file_type}, {file_ext})")
                FilePreviewComponent._render_generic(file_bytes, file_ext)
        except Exception as e:
            logger.error(f"Необработанная ошибка при рендеринге {file_name}: {e}", exc_info=True)
            st.error("Произошла непредвиденная ошибка при отображении файла.")

    @staticmethod
    def _show_metadata(file_name: str, file_type: str, file_ext: str):
        st.write(f"**Имя файла:** `{file_name}`")
        st.write(f"**Тип:** `{file_type}`")
        st.write(f"**Расширение:** `{file_ext}`")

    @staticmethod
    def _render_image(file_bytes: bytes):
        try:
            st.image(file_bytes, caption="Изображение", width='stretch')
            logger.debug("Изображение успешно отображено")
        except Exception as e:
            logger.error(f"Ошибка отображения изображения: {e}")
            st.error(f"Ошибка отображения изображения: {e}")

    @staticmethod
    def _render_pdf(file_bytes: bytes, file_name: str):
        try:
            pdf_doc = fitz.open(stream=BytesIO(file_bytes), filetype="pdf")
            page_count = pdf_doc.page_count
            logger.debug(f"PDF открыт: {page_count} страниц")

            if page_count == 0:
                st.warning("PDF не содержит страниц.")
                pdf_doc.close()
                return

            page_num_input = st.number_input(
                "Номер страницы",
                min_value=1,
                max_value=page_count,
                value=1,
                step=1,
                key=f"pdf_page_{file_name}"
            )
            page_num = page_num_input - 1

            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=Config.DEFAULT_DPI)
            img_data = pix.tobytes("png")
            st.image(img_data, caption=f"Страница {page_num + 1} из {page_count}", width='stretch')
            logger.debug(f"Отображена страница {page_num + 1} PDF")

            pdf_doc.close()
        except Exception as e:
            logger.error(f"Ошибка при открытии PDF '{file_name}': {e}", exc_info=True)
            st.error(f"Ошибка при открытии PDF: {e}")

    @staticmethod
    def _render_docx(file_bytes: bytes, file_name: str):
        try:
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            logger.debug(f"DOCX загружен: {len(paragraphs)} непустых параграфов")

            if not paragraphs:
                st.info("Документ пуст.")
                return

            PARAGRAPHS_PER_PAGE = 30
            total_pages = (len(paragraphs) + PARAGRAPHS_PER_PAGE - 1) // PARAGRAPHS_PER_PAGE

            page_num_input = st.number_input(
                "Страница (по параграфам)",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
                key=f"docx_page_{file_name}"
            )

            start_idx = (page_num_input - 1) * PARAGRAPHS_PER_PAGE
            end_idx = start_idx + PARAGRAPHS_PER_PAGE
            page_paragraphs = paragraphs[start_idx:end_idx]

            st.markdown("### Содержимое:")
            for para in page_paragraphs:
                st.markdown(f"{para}")

            st.caption(f"Параграфы {start_idx + 1}–{min(end_idx, len(paragraphs))} из {len(paragraphs)}")
            logger.debug(f"Отображена страница {page_num_input} DOCX")
        except Exception as e:
            logger.error(f"Ошибка при чтении DOCX '{file_name}': {e}", exc_info=True)
            st.error(f"Ошибка при чтении DOCX: {e}")

    @staticmethod
    def _render_generic(file_bytes: bytes, file_ext: str):
        st.info("Предпросмотр недоступен для этого типа файла.")
        if isinstance(file_bytes, bytes) and len(file_bytes) < 10000:
            try:
                text_content = file_bytes.decode('utf-8')
                st.text_area("Содержимое файла", text_content, height=300)
                logger.debug("Отображено текстовое содержимое неподдерживаемого файла")
            except UnicodeDecodeError:
                logger.debug("Файл не является текстовым — содержимое не показано")
            except Exception as e:
                logger.warning(f"Ошибка при попытке отобразить содержимое: {e}")

    @staticmethod
    def render_file_info_and_page_selector(shared_file: dict, session_state_key_prefix: str = "file_display") -> int:
        """
        Отображает информацию о файле (имя, иконка) и, если это PDF, позволяет выбрать страницу.
        Управляет состоянием выбора страницы через session_state с уникальным префиксом.

        Args:
            shared_file (dict): Словарь с информацией о файле ('name', 'type', 'ext', 'bytes').
            session_state_key_prefix (str): Префикс для ключей session_state, чтобы избежать коллизий.
                                             Например, 'rotation', 'binary'.

        Returns:
            int: Номер выбранной страницы (0-indexed) или 0, если файл не PDF или ошибка.
        """
        # Отображение базовой информации о файле
        icon = get_file_icon(shared_file["type"], shared_file["ext"])
        st.info(f"{icon} Работаем с файлом: **{shared_file['name']}**")

        selected_page_num = 0  # По умолчанию первая страница (0-indexed)

        # Выбор страницы для PDF
        if Config.is_pdf_file(shared_file["type"], shared_file["ext"]):
            selected_page_num = FilePreviewComponent._show_pdf_page_selector_internal(
                shared_file, session_state_key_prefix
            )
        else:
            logger.debug(f"Файл {shared_file['name']} не является PDF, выбор страницы пропущен.")

        return selected_page_num

    @staticmethod
    def _show_pdf_page_selector_internal(shared_file: dict, key_prefix: str) -> int:
        """
        Приватный метод для отображения селектора страницы PDF.
        """
        try:
            logger.debug(f"Загрузка PDF для получения количества страниц: {shared_file['name']}")
            pdf_doc = fitz.open(stream=BytesIO(shared_file["bytes"]), filetype="pdf")
            page_count = pdf_doc.page_count
            pdf_doc.close()

            if page_count <= 0:
                st.warning("📄 PDF не содержит страниц.")
                return 0

            if page_count == 1:
                st.info("📄 PDF содержит одну страницу.")
                return 0  # Всегда 0 для одиночной страницы

            # Используем уникальный ключ для session_state
            page_selector_key = f"{key_prefix}_pdf_page_selector"

            # Проверяем, установлено ли уже состояние, иначе устанавливаем по умолчанию
            if page_selector_key not in st.session_state:
                st.session_state[page_selector_key] = 0

            page_num_1_indexed = st.number_input(
                "Выберите страницу для обработки:",
                min_value=1,
                max_value=page_count,
                value=st.session_state[page_selector_key] + 1, # Отображаем 1-indexed
                step=1,
                key=page_selector_key
            )

            # Обновляем session_state, если пользователь выбрал другую страницу
            selected_page_num_0_indexed = page_num_1_indexed - 1
            if st.session_state[page_selector_key] != selected_page_num_0_indexed:
                 st.session_state[page_selector_key] = selected_page_num_0_indexed
                 logger.info(f"Выбрана страница {selected_page_num_0_indexed + 1} для файла {shared_file['name']}.")

            logger.debug(f"PDF страница выбрана: {selected_page_num_0_indexed} (0-indexed)")
            return selected_page_num_0_indexed

        except Exception as e:
            logger.error(f"Ошибка при обработке PDF '{shared_file['name']}': {e}", exc_info=True)
            st.error(f"❌ Ошибка при чтении PDF документа: {e}")
            return 0 # Возвращаем 0 в случае ошибки
