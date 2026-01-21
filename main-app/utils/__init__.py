# utils/__init__.py
# Сначала импорты
from .errors import (
    APIError,
    FileProcessingError,
    ValidationError,
    ImageProcessingError,  # Новое исключение
    error_handler
)
from .file_utils import (
    get_file_metadata,
    format_file_size,
    get_file_icon
)
from .image_utils import convert_file_to_image
from .validation import (
    validate_threshold,
    validate_line_detection_params,
    validate_rotation_angle,
    validate_file_upload
)
from config import Config


# Определяем функции-обертки ДО __all__
def handle_api_error(error: Exception, operation_name: str = "операция"):
    """Универсальный обработчик ошибок API"""
    return error_handler.handle_api_error(error, operation_name)


def handle_file_error(error: Exception, file_name: str = "файл"):
    """Универсальный обработчик ошибок файлов"""
    return error_handler.handle_file_error(error, file_name)


def handle_image_processing_error(error: Exception, operation_name: str = "обработка"):
    """Универсальный обработчик ошибок обработки изображений"""
    return error_handler.handle_image_processing_error(error, operation_name)


def show_success(message: str, operation_name: str = "операция"):
    """Показать сообщение об успехе"""
    return error_handler.show_success_message(message, operation_name)


# Псевдонимы для функций из Config (ОПРЕДЕЛЕНЫ ДО __all__)
is_image_file = Config.is_image_file
is_pdf_file = Config.is_pdf_file
is_docx_file = Config.is_docx_file
is_supported_file = Config.is_supported_file_type

# Теперь включаем ВСЕ публичные имена в __all__
__all__ = [
    # errors
    "APIError",
    "FileProcessingError",
    "ValidationError",
    "ImageProcessingError",  # Новое исключение
    "error_handler",

    # error handlers (функции-обертки)
    "handle_api_error",
    "handle_file_error",
    "handle_image_processing_error",
    "show_success",

    # file_utils
    "get_file_metadata",
    "format_file_size",
    "get_file_icon",

    # image_utils
    "convert_file_to_image",

    # validation
    "validate_threshold",
    "validate_line_detection_params",
    "validate_rotation_angle",
    "validate_file_upload",

    # config functions
    "Config",
    "is_image_file",
    "is_pdf_file",
    "is_docx_file",
    "is_supported_file"
]