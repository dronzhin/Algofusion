# core/services/file_service.py
"""
Сервис для работы с файлами.
Общая логика для всех контейнеров.
"""

import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from shared.models.file import FileJob, FileStatus
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir

logger = setup_logger("core.services.file_service")


class FileService:
    """Сервис для управления файлами и папками."""

    def __init__(self, base_dir: str = "/shared/files"):
        self.base_dir = Path(base_dir)
        safe_mkdir(self.base_dir)
        logger.info(f"FileService инициализирован: base_dir={self.base_dir}")

    def create_file_structure(self, file_job: FileJob) -> bool:
        """Создание структуры папок для файла."""
        try:
            base = file_job.get_base_path(str(self.base_dir))

            directories = [
                base / "original",
                base / "preprocessed",
                base / "ocr",
                base / "llm",
                base / "export",
                base / "archive"
            ]

            for dir_path in directories:
                safe_mkdir(dir_path)

            logger.info(f"Структура папок создана для файла {file_job.file_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания структуры папок: {e}", exc_info=True)
            return False

    def move_to_archive(self, file_job: FileJob) -> bool:
        """Перемещение файлов в архив после обработки."""
        try:
            base = file_job.get_base_path(str(self.base_dir))
            archive_path = file_job.get_archive_path(str(self.base_dir))

            # Создаём ZIP архив
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for folder in ["original", "preprocessed", "ocr", "llm", "export"]:
                    folder_path = base / folder
                    if folder_path.exists():
                        for file_path in folder_path.rglob("*"):
                            if file_path.is_file():
                                arcname = file_path.relative_to(base)
                                zipf.write(file_path, arcname)

            logger.info(f"Файл {file_job.file_id} архивирован: {archive_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка архивации файла {file_job.file_id}: {e}", exc_info=True)
            return False

    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о файле."""
        try:
            base = self.base_dir / file_id
            if not base.exists():
                return None

            info = {
                "file_id": file_id,
                "base_path": str(base),
                "directories": {}
            }

            for folder in ["original", "preprocessed", "ocr", "llm", "export", "archive"]:
                folder_path = base / folder
                if folder_path.exists():
                    files = list(folder_path.rglob("*"))
                    info["directories"][folder] = {
                        "path": str(folder_path),
                        "file_count": len([f for f in files if f.is_file()]),
                        "files": [f.name for f in files if f.is_file()]
                    }

            return info
        except Exception as e:
            logger.error(f"Ошибка получения информации о файле {file_id}: {e}", exc_info=True)
            return None

    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """Очистка старых файлов."""
        try:
            cleaned = 0
            now = datetime.utcnow()

            for file_dir in self.base_dir.iterdir():
                if file_dir.is_dir() and file_dir.name != "archive":
                    # Проверяем возраст по времени создания директории
                    created = datetime.fromtimestamp(file_dir.stat().st_ctime)
                    age = (now - created).days

                    if age > max_age_days:
                        shutil.rmtree(file_dir)
                        cleaned += 1
                        logger.info(f"Удалён старый файл: {file_dir.name} ({age} дней)")

            logger.info(f"Очистка завершена: удалено {cleaned} файлов")
            return cleaned
        except Exception as e:
            logger.error(f"Ошибка очистки старых файлов: {e}", exc_info=True)
            return 0

    def list_files(self) -> List[str]:
        """Список всех файлов в обработке."""
        try:
            return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов: {e}")
            return []