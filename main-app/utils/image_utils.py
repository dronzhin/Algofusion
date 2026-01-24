# utils/image_utils.py
from PIL import Image
import fitz  # PyMuPDF
from io import BytesIO
from typing import Optional
from config import Config


def convert_file_to_image(file_bytes: bytes, file_type: str, file_ext: str, page_num: int = 0) -> Optional[bytes]:
    """
    Универсальная функция для конвертации файлов в изображения
    """
    try:
        if Config.is_pdf_file(file_type, file_ext):
            return _convert_pdf_to_image(file_bytes, page_num)
        elif Config.is_image_file(file_type, file_ext):
            return _convert_image_to_png(file_bytes)
        return None
    except Exception as e:
        print(f"Error converting file to image: {e}")
        return None


def _convert_pdf_to_image(pdf_bytes: bytes, page_num: int = 0) -> Optional[bytes]:
    """Конвертация PDF страницы в изображение"""
    try:
        pdf_doc = fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf")
        if page_num >= pdf_doc.page_count:
            page_num = 0

        page = pdf_doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        pdf_doc.close()
        return img_data
    except Exception as e:
        raise Exception(f"Ошибка конвертации PDF: {e}") from e


def _convert_image_to_png(image_bytes: bytes) -> Optional[bytes]:
    """Конвертация изображения в PNG формат"""
    try:
        img = Image.open(BytesIO(image_bytes))
        img.load()

        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        raise Exception(f"Ошибка конвертации изображения: {e}") from e