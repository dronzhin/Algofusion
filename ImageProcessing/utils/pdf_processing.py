from pdf2image import convert_from_bytes
import io
from PIL import Image
import base64


def convert_pdf_to_images(pdf_bytes: bytes) -> list:
    """
    Конвертирует PDF в список изображений

    Args:
        pdf_bytes: Байты PDF файла

    Returns:
        Список изображений (PIL Image)
    """
    try:
        return convert_from_bytes(pdf_bytes)
    except Exception as e:
        raise ValueError(f"Ошибка конвертации PDF: {str(e)}")


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
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
            base64_list.append(base64_str)
        return base64_list
    except Exception as e:
        raise ValueError(f"Ошибка конвертации изображений в base64: {str(e)}")