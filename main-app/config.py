# config.py
import os
from typing import Dict, Any, Set


class Config:
    """
    Централизованная конфигурация приложения
    Все проверки типов файлов теперь здесь
    """

    # API настройки
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))

    # Поддерживаемые форматы файлов
    SUPPORTED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    SUPPORTED_IMAGE_TYPES: Set[str] = {"image/jpeg", "image/jpg", "image/png", "image/bmp", "image/gif"}

    SUPPORTED_PDF_EXTENSIONS: Set[str] = {".pdf"}
    SUPPORTED_PDF_TYPES: Set[str] = {"application/pdf"}

    SUPPORTED_DOCX_EXTENSIONS: Set[str] = {".docx"}
    SUPPORTED_DOCX_TYPES: Set[str] = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS | SUPPORTED_DOCX_EXTENSIONS
    SUPPORTED_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_PDF_TYPES | SUPPORTED_DOCX_TYPES

    # === Параметры обработки изображений ===
    DEFAULT_DPI = 150
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    # Бинаризация
    DEFAULT_BINARY_THRESHOLD = 128

    # Детекция линий (выравнивание)
    DEFAULT_MIN_LINE_LENGTH = 50
    DEFAULT_MAX_LINE_GAP = 40
    DEFAULT_USE_MORPHOLOGY = True

    # Настройки сессии
    SESSION_TIMEOUT_MINUTES = 30

    @classmethod
    def get_rotation_default_params(cls) -> Dict[str, Any]:
        return {
            "min_line_length": cls.DEFAULT_MIN_LINE_LENGTH,
            "max_line_gap": cls.DEFAULT_MAX_LINE_GAP,
            "use_morphology": cls.DEFAULT_USE_MORPHOLOGY
        }

    @classmethod
    def get_api_config(cls) -> Dict[str, Any]:
        """Получить конфигурацию для API клиента"""
        return {
            "base_url": cls.API_BASE_URL,
            "timeout": cls.API_TIMEOUT,
            "max_retries": cls.API_MAX_RETRIES
        }

    @classmethod
    def is_image_file(cls, file_type: str, file_ext: str) -> bool:
        """
        Проверить, является ли файл изображением
        """
        file_ext = file_ext.lower()
        return (file_type in cls.SUPPORTED_IMAGE_TYPES or
                file_ext in cls.SUPPORTED_IMAGE_EXTENSIONS)

    @classmethod
    def is_pdf_file(cls, file_type: str, file_ext: str) -> bool:
        """
        Проверить, является ли файл PDF
        """
        file_ext = file_ext.lower()
        return (file_type in cls.SUPPORTED_PDF_TYPES or
                file_ext in cls.SUPPORTED_PDF_EXTENSIONS)

    @classmethod
    def is_docx_file(cls, file_type: str, file_ext: str) -> bool:
        """
        Проверить, является ли файл DOCX
        """
        file_ext = file_ext.lower()
        return (file_type in cls.SUPPORTED_DOCX_TYPES or
                file_ext in cls.SUPPORTED_DOCX_EXTENSIONS)

    @classmethod
    def is_image_like_file(cls, file_type: str, file_ext: str) -> bool:
        """
        Проверяет, является ли файл 'изображением' в широком смысле:
        - растровые изображения (JPG, PNG и т.д.)
        - PDF (может содержать изображения или сканы)

        Используется для всех инструментов обработки изображений:
        выравнивание, бинаризация, OCR и др.
        """
        return cls.is_image_file(file_type, file_ext) or cls.is_pdf_file(file_type, file_ext)

