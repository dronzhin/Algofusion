# utils/pdf_processing.py
"""
Утилиты для обработки PDF
"""
from pdf2image import convert_from_bytes
import io
import base64
from utils.logging_config import get_logger

logger = get_logger(__name__)

def convert_pdf_to_images(pdf_bytes: bytes) -> list:
    """
    Конвертирует PDF в список изображений

    Args:
        pdf_bytes: Байты PDF файла

    Returns:
        Список изображений (PIL Image)
    """
    try:
        logger.info(f"Конвертация PDF, размер: {len(pdf_bytes)} байт")
        images = convert_from_bytes(pdf_bytes)
        logger.info(f"PDF успешно конвертирован в {len(images)} изображений")
        return images
    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка конвертации PDF: {safe_error}")
        raise ValueError(f"Ошибка конвертации PDF: {safe_error}")


def images_to_base64(images: list) -> list:
    """
    Конвертирует список изображений в base64

    Args:
        images: Список изображений PIL

    Returns:
        Список строк base64
    """
    try:
        base64_list = []
        for i, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
            base64_list.append(base64_str)
            logger.debug(f"Изображение {i+1}/{len(images)} сконвертировано в base64")
        return base64_list
    except Exception as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка конвертации изображений в base64: {safe_error}")
        raise ValueError(f"Ошибка конвертации изображений в base64: {safe_error}")