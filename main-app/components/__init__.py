# components/__init__.py
from .file_preview import FilePreviewComponent
from .settings_panel import SettingsPanel
from .ui_helpers import show_unsupported_file_error, show_download_button, select_page_number_ui
from .error_handler import error_handler
from .image_comparison import ImageComparisonComponent
from .OCRResultComponent import render_ocr_result, show_server_unavailable, show_model_selection  # ← ДОБАВЛЕНО

# Создаём класс-обёртку для удобного импорта
class OCRResultComponent:
    render_ocr_result = staticmethod(render_ocr_result)
    show_server_unavailable = staticmethod(show_server_unavailable)
    show_model_selection = staticmethod(show_model_selection)

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
    "ImageComparisonComponent",
    "show_download_button",
    "select_page_number_ui",
    "OCRResultComponent",  # ← ДОБАВЛЕНО
    # error handlers (функции-обертки)
    "handle_api_error",
    "handle_file_error",
    "handle_image_processing_error",
    "show_success",
]