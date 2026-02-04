# utils/pdf_handler.py

"""
Модуль для обработки многостраничных PDF файлов.
Конвертирует PDF в изображения для последующего распознавания текста.
"""

from utils import logger
import fitz  # PyMuPDF
from PIL import Image
import io
from typing import List, Tuple


class PDFHandler:
    """Обработчик многостраничных PDF файлов"""

    def __init__(self, dpi: int = 300):
        """
        Инициализация обработчика PDF

        Args:
            dpi: разрешение при конвертации (рекомендуется 200-300 для качественного распознавания)
        """
        self.dpi = dpi
        logger.debug(f"PDFHandler инициализирован | DPI: {dpi}")

    def pdf_bytes_to_images(self, pdf_bytes: bytes) -> List[Tuple[int, Image.Image]]:
        """
        Конвертация байтов PDF в список изображений (по одному на страницу)

        Args:
            pdf_bytes: байты PDF файла

        Returns:
            Список кортежей (номер страницы, PIL Image)
        """
        import time
        start = time.time()

        try:
            # Открываем PDF документ
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(pdf_document)

            logger.info(f"📄 Обнаружен многостраничный PDF | Страниц: {total_pages}")

            images = []

            for page_num in range(total_pages):
                try:
                    # Получаем страницу
                    page = pdf_document[page_num]

                    # Конвертируем страницу в изображение
                    # dpi -> zoom: 72 DPI = 1.0 zoom, 300 DPI = 300/72 ≈ 4.17
                    zoom = self.dpi / 72
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)

                    # Конвертируем в PIL Image
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    images.append((page_num + 1, img))

                    logger.debug(f"   ✅ Страница {page_num + 1}/{total_pages} конвертирована | Размер: {img.size}")

                except Exception as e:
                    logger.error(f"   ❌ Ошибка обработки страницы {page_num + 1}: {str(e)}", exc_info=True)
                    # Продолжаем обработку остальных страниц
                    continue

            pdf_document.close()

            elapsed = time.time() - start
            logger.info(f"✅ PDF обработан за {elapsed:.2f} сек | Страниц обработано: {len(images)}/{total_pages}")

            return images

        except Exception as e:
            logger.error(f"❌ Ошибка обработки PDF: {str(e)}", exc_info=True)
            raise ValueError(f"Невозможно обработать PDF файл: {str(e)}")

    def pdf_file_to_images(self, file_path: str) -> List[Tuple[int, Image.Image]]:
        """
        Конвертация PDF файла по пути в список изображений

        Args:
            file_path: путь к файлу PDF

        Returns:
            Список кортежей (номер страницы, PIL Image)
        """
        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            return self.pdf_bytes_to_images(pdf_bytes)
        except Exception as e:
            logger.error(f"❌ Ошибка чтения PDF файла: {str(e)}", exc_info=True)
            raise