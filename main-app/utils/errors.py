# utils/errors.py
"""
Система исключений для приложения.
Все специализированные исключения наследуются от базовых для совместимости с существующим кодом.
"""

from typing import Any, Optional


class APIError(Exception):
    """
    Базовое исключение для ошибок взаимодействия с API.
    Совместимо с существующим кодом и error_handler.py.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Any = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)

    def __str__(self):
        if self.status_code:
            return f"APIError ({self.status_code}): {self.message}"
        return f"APIError: {self.message}"


class OCRServerError(APIError):
    """
    Специализированное исключение для ошибок сервера распознавания текста.
    Полностью совместимо с базовым APIError — существующий код продолжит работать.
    """

    def __init__(
            self,
            message: str,
            status_code: Optional[int] = None,
            response_data: Any = None,
            endpoint: str = "/ocr",
            model_name: Optional[str] = None
    ):
        super().__init__(message, status_code, response_data)
        self.endpoint = endpoint
        self.model_name = model_name

    def __str__(self):
        base = super().__str__()
        extras = []
        if self.endpoint:
            extras.append(f"endpoint={self.endpoint}")
        if self.model_name:
            extras.append(f"model={self.model_name}")
        if extras:
            return f"{base} [{' | '.join(extras)}]"
        return base


class PreprocessingServerError(APIError):
    """
    Специализированное исключение для ошибок сервера предобработки изображений.
    Полностью совместимо с базовым APIError.
    """

    def __init__(
            self,
            message: str,
            status_code: Optional[int] = None,
            response_data: Any = None,
            operation: str = "unknown"
    ):
        super().__init__(message, status_code, response_data)
        self.operation = operation

    def __str__(self):
        base = super().__str__()
        return f"{base} [operation={self.operation}]"


class FileProcessingError(Exception):
    """Ошибка обработки файла"""
    pass


class ValidationError(Exception):
    """Ошибка валидации данных"""
    pass


class ImageProcessingError(Exception):
    """Ошибка обработки изображения"""
    pass


# ==================== УТИЛИТЫ ДЛЯ РАБОТЫ С ИСКЛЮЧЕНИЯМИ ====================

def is_ocr_error(error: Exception) -> bool:
    """Проверка, является ли ошибка связанной с распознаванием текста"""
    return isinstance(error, OCRServerError) or (
            isinstance(error, APIError) and
            hasattr(error, 'endpoint') and
            error.endpoint in ['/ocr', '/models']
    )


def is_preprocessing_error(error: Exception) -> bool:
    """Проверка, является ли ошибка связанной с предобработкой"""
    return isinstance(error, PreprocessingServerError) or (
            isinstance(error, APIError) and
            hasattr(error, 'operation') and
            error.operation in ['convert', 'rotate']
    )


def get_error_category(error: Exception) -> str:
    """
    Определение категории ошибки для логирования и аналитики

    Возвращает: 'ocr', 'preprocessing', 'file', 'validation', 'image', 'unknown'
    """
    if is_ocr_error(error):
        return 'ocr'
    elif is_preprocessing_error(error):
        return 'preprocessing'
    elif isinstance(error, FileProcessingError):
        return 'file'
    elif isinstance(error, ValidationError):
        return 'validation'
    elif isinstance(error, ImageProcessingError):
        return 'image'
    else:
        return 'unknown'