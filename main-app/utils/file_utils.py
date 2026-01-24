# utils/file_utils.py
from pathlib import Path
from typing import Dict, Any, Optional
from config import Config  # Теперь импортируем отсюда


def get_file_metadata(uploaded_file) -> Dict[str, Any]:
    """
    Получить метаданные файла
    """
    if uploaded_file is None:
        return {}

    file_path = Path(uploaded_file.name)
    return {
        "name": uploaded_file.name,
        "stem": file_path.stem,
        "ext": file_path.suffix.lower(),
        "size_bytes": uploaded_file.size,
        "size_mb": round(uploaded_file.size / (1024 * 1024), 2),
        "mime_type": uploaded_file.type,
        "is_image": Config.is_image_file(uploaded_file.type, file_path.suffix.lower()),
        "is_pdf": Config.is_pdf_file(uploaded_file.type, file_path.suffix.lower()),
        "is_docx": Config.is_docx_file(uploaded_file.type, file_path.suffix.lower())
    }

def format_file_size(size_bytes: int) -> str:
    """
    Форматировать размер файла
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_file_icon(file_type: str, file_ext: str) -> str:
    """
    Получить иконку для типа файла
    """
    if Config.is_image_file(file_type, file_ext):
        return "🖼️"
    elif Config.is_pdf_file(file_type, file_ext):
        return "📄"
    elif Config.is_docx_file(file_type, file_ext):
        return "📝"
    elif file_ext.lower() in [".txt", ".csv", ".json"]:
        return "📋"
    else:
        return "📁"