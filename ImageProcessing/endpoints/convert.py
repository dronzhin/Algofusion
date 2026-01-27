# endpoints/convert.py
"""
Эндпоинт для конвертации изображений
"""
from fastapi import UploadFile, HTTPException
from typing import Dict, List, Union
import io
from PIL import Image
from utils import binary_convert, convert_pdf_to_images, get_logger  # Используем импорт через __init__.py
import base64
import traceback

logger = get_logger(__name__)


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
        logger.info(f"Получен файл: {file.filename}, размер: {len(contents)} байт, content_type: {file.content_type}")

        # Расширенный список поддерживаемых типов файлов
        SUPPORTED_IMAGE_TYPES = [
            "image/jpeg", "image/jpg", "image/png", "image/bmp", "image/gif",
            "image/x-png", "image/pjpeg", "image/x-jpg", "image/webp"
        ]
        SUPPORTED_DOCUMENT_TYPES = ["application/pdf"]

        # Проверяем тип файла более гибко
        is_supported = False
        file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ""

        if file.content_type in SUPPORTED_IMAGE_TYPES or file_ext in ["jpg", "jpeg", "png", "bmp", "gif", "webp"]:
            is_supported = True
            logger.info(f"Поддерживаемый тип изображения: {file.content_type}, расширение: {file_ext}")
        elif file.content_type in SUPPORTED_DOCUMENT_TYPES or file_ext == "pdf":
            is_supported = True
            logger.info(f"Поддерживаемый тип документа: {file.content_type}, расширение: {file_ext}")
        else:
            logger.warning(f"Неподдерживаемый тип файла: content_type={file.content_type}, расширение={file_ext}")
            raise HTTPException(status_code=400,
                                detail=f"Неподдерживаемый тип файла. Поддерживаются: JPG, PNG, BMP, GIF, PDF. Получен: {file.content_type} ({file_ext})")

        # Обработка в зависимости от типа файла
        if file.content_type == "application/pdf" or file_ext == "pdf":
            logger.info("Конвертация PDF файла")
            # Конвертируем PDF в изображения
            images = convert_pdf_to_images(contents)
            logger.info(f"PDF сконвертирован в {len(images)} изображений")
        else:
            logger.info("Обработка изображения")
            # Открываем как изображение
            img = Image.open(io.BytesIO(contents))
            images = [img]
            logger.info(f"Загружено изображение: {img.format}, размер: {img.size}, mode: {img.mode}")

        # Конвертируем каждое изображение в бинарный формат
        binary_images = []
        for i, img in enumerate(images):
            logger.debug(f"Обработка изображения {i + 1}/{len(images)}")
            # Конвертируем в байты для обработки
            img_buffer = io.BytesIO()
            # Убедимся, что изображение в правильном формате
            if img.mode not in ('RGB', 'L'):
                logger.debug(f"Конвертация изображения из режима {img.mode} в RGB")
                img = img.convert('RGB')
            img.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()

            # Применяем бинаризацию
            binary_bytes = binary_convert(img_bytes, threshold)
            binary_images.append(binary_bytes)
            logger.debug(f"Изображение {i + 1} успешно бинаризовано")

        # Конвертируем в base64
        base64_list = []
        for i, binary_bytes in enumerate(binary_images):
            base64_str = base64.b64encode(binary_bytes).decode('utf-8')
            base64_list.append(base64_str)
            logger.debug(f"Изображение {i + 1} сконвертировано в base64, длина: {len(base64_str)}")

        return {"images_base64": base64_list, "count": len(base64_list), "success": True}

    except HTTPException:
        # Перехватываем HTTP исключения и пропускаем их дальше
        raise
    except ValueError as e:
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        logger.error(f"Ошибка валидации: {safe_error}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=safe_error)
    except Exception as e:
        logger.error(f"Критическая ошибка обработки: {str(e)}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")
        safe_error = str(e).encode('utf-8', 'ignore').decode('utf-8')
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {safe_error}")