# components/__init__.py
from .file_preview import FilePreviewComponent
from .settings_panel import SettingsPanel
from .ui_helpers import show_unsupported_file_error
from .error_handler import error_handler

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

__all__ = [
    "FilePreviewComponent",
    "SettingsPanel",
    "show_unsupported_file_error",

    # error handlers (функции-обертки)
    "handle_api_error",
    "handle_file_error",
    "handle_image_processing_error",
    "show_success",
]