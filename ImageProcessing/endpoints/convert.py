from fastapi import UploadFile, HTTPException
from typing import Dict, List, Union
import io
from PIL import Image
from utils.image_processing import binary_convert
from utils.pdf_processing import convert_pdf_to_images, images_to_base64
import base64


async def convert_image_endpoint(file: UploadFile, threshold: int = 128) -> Dict[str, Union[List[str], str]]:
    """
    Обработчик эндпоинта /convert

    Args:
        file: Загруженный файл
        threshold: Порог бинаризации

    Returns:
        Словарь с результатами
    """
    try:
        # Читаем содержимое файла
        contents = await file.read()

        # Проверяем тип файла
        if not file.content_type.startswith(("image/", "application/pdf")):
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип файла")

        # Обработка в зависимости от типа файла
        if file.content_type == "application/pdf":
            # Конвертируем PDF в изображения
            images = convert_pdf_to_images(contents)
        else:
            # Открываем как изображение
            img = Image.open(io.BytesIO(contents))
            images = [img]

        # Конвертируем каждое изображение в бинарный формат
        binary_images = []
        for img in images:
            # Конвертируем в байты для обработки
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()

            # Применяем бинаризацию
            binary_bytes = binary_convert(img_bytes, threshold)
            binary_images.append(binary_bytes)

        # Конвертируем в base64
        base64_list = []
        for binary_bytes in binary_images:
            base64_str = base64.b64encode(binary_bytes).decode('utf-8')
            base64_list.append(base64_str)

        return {"images_base64": base64_list}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")