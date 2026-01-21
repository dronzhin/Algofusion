import streamlit as st
from typing import Dict, Any, Optional
from pathlib import Path
from config import Config


class FileService:
    """
    Сервис для работы с файлами
    Инкапсулирует логику загрузки, валидации и обработки файлов
    """

    @staticmethod
    def validate_file(file_info: Dict[str, Any]) -> bool:
        """
        Валидация загруженного файла
        """
        file_size = file_info["size"]
        file_type = file_info["type"]
        file_ext = file_info["ext"].lower()

        # Проверка размера
        if file_size > Config.MAX_IMAGE_SIZE:
            st.warning(f"⚠️ Файл слишком большой (максимум {Config.MAX_IMAGE_SIZE // (1024 * 1024)}MB)")
            return False

        # Проверка типа файла
        if not Config.is_supported_file_type(file_type, file_ext):
            st.warning(f"❌ Неподдерживаемый тип файла: {file_type} ({file_ext})")
            st.info(f"Поддерживаются: {', '.join(Config.SUPPORTED_TYPES)}")
            return False

        return True

    @staticmethod
    def process_uploaded_file(uploaded_file) -> Optional[Dict[str, Any]]:
        """
        Обработка загруженного файла
        """
        if uploaded_file is None:
            return None

        file_name = uploaded_file.name
        file_ext = Path(file_name).suffix.lower()

        file_info = {
            "name": file_name,
            "bytes": uploaded_file.getvalue(),
            "type": uploaded_file.type,
            "ext": file_ext,
            "size": uploaded_file.size
        }

        if not FileService.validate_file(file_info):
            return None

        return file_info

    @staticmethod
    def get_file_preview_config(file_type: str, file_ext: str) -> Dict[str, Any]:
        """
        Получить конфигурацию для предпросмотра файла
        """
        config = {
            "show_metadata": True,
            "use_column_width": True
        }

        if file_type == "application/pdf" or file_ext == ".pdf":
            config.update({
                "dpi": Config.DEFAULT_DPI,
                "show_page_selector": True
            })
        elif file_type.startswith("image/") or file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
            config.update({
                "show_metadata": True,
                "caption": "Изображение"
            })
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_ext == ".docx":
            config.update({
                "paragraphs_per_page": 30,
                "show_page_selector": True
            })

        return config