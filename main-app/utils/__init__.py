# utils/__init__.py
from .errors import (
    APIError,
    FileProcessingError,
    ValidationError,
    ImageProcessingError,  # Новое исключение
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
from .logger import setup_app_logger

# Теперь включаем ВСЕ публичные имена в __all__
__all__ = [
    # errors
    "APIError",
    "FileProcessingError",
    "ValidationError",
    "ImageProcessingError",  # Новое исключение

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

    # logging
    "setup_app_logger"
]