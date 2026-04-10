# core/services/file_service.py
"""
Сервис для работы с файлами.
Общая логика для всех контейнеров.
"""

import shutil
import zipfile
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from shared.models.file import FileJob
from shared.utils.logger import setup_logger
from shared.utils.helpers import (
    safe_mkdir,
    format_file_size,
    format_datetime,
    get_file_fingerprint,
    get_safe_file_path,
    is_file_already_processed,
    cleanup_orphaned_jobs
)

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
            info = {"file_id": file_id, "base_path": str(base), "directories": {}}
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
            now = datetime.now(timezone.utc)
            for file_dir in self.base_dir.iterdir():
                if file_dir.is_dir() and file_dir.name != "archive":
                    created = datetime.fromtimestamp(file_dir.stat().st_ctime, tz=timezone.utc)
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

    def get_download_path(self, file_id: str, file_type: str = "original") -> Optional[Path]:
        """Возвращает путь к файлу для скачивания."""
        try:
            base = self.base_dir / file_id
            folder_map = {
                "original": "original", "preprocessed": "preprocessed",
                "ocr": "ocr", "llm": "llm", "export": "export"
            }
            folder = folder_map.get(file_type, "original")
            folder_path = base / folder
            if folder_path.exists():
                files = [f for f in folder_path.rglob("*") if f.is_file()]
                return files[0] if files else None
            return None
        except Exception as e:
            logger.error(f"Ошибка получения пути для скачивания: {e}")
            return None

    def get_file_content(self, file_id: str, file_type: str = "original") -> Optional[bytes]:
        """Читает содержимое файла для предпросмотра (макс. 15 МБ)."""
        try:
            path = self.get_download_path(file_id, file_type)
            if path and path.exists():
                max_size = 1024 * 1024 * 15
                if path.stat().st_size > max_size:
                    logger.warning(f"Файл слишком большой для предпросмотра: {path}")
                    return None
                return path.read_bytes()
            return None
        except Exception as e:
            logger.error(f"Ошибка чтения файла: {e}")
            return None

    def get_text_preview(self, file_id: str, file_type: str = "ocr", max_lines: int = 50) -> Optional[str]:
        """Возвращает текстовый превью файла."""
        try:
            content = self.get_file_content(file_id, file_type)
            if content:
                text = content.decode("utf-8", errors="replace")
                lines = text.split("\n")[:max_lines]
                return "\n".join(lines)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения текстового превью: {e}")
            return None

    def get_file_metadata(self, file_id: str, file_type: str = "original") -> Optional[Dict[str, Any]]:
        """Возвращает метаданные файла."""
        try:
            path = self.get_download_path(file_id, file_type)
            if path and path.exists():
                stat = path.stat()
                return {
                    "filename": path.name,
                    "size_bytes": stat.st_size,
                    "size_human": format_file_size(stat.st_size),
                    "created": format_datetime(datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)),
                    "modified": format_datetime(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                    "mime_type": self._guess_mime_type(path),
                    "is_image": path.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp"],
                    "is_text": path.suffix.lower() in [".txt", ".md", ".json", ".csv", ".xml"],
                    "is_pdf": path.suffix.lower() == ".pdf",
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения метаданных: {e}")
            return None

    def delete_file(self, file_id: str, force: bool = False) -> bool:
        """Удаляет файл и его структуру."""
        try:
            base = self.base_dir / file_id
            if not base.exists():
                logger.warning(f"Файл не найден для удаления: {file_id}")
                return False
            if not force:
                status_file = base / "status.json"
                if status_file.exists():
                    with open(status_file) as f:
                        status = json.load(f).get("status", "")
                    if status in ["processing", "uploaded"]:
                        logger.warning(f"Файл {file_id} в обработке, удаление отклонено")
                        return False
            shutil.rmtree(base)
            logger.info(f"Файл удалён: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления файла {file_id}: {e}")
            return False

    def retry_processing(self, file_id: str) -> bool:
        """Сбрасывает статус файла для повторной обработки."""
        try:
            base = self.base_dir / file_id
            status_file = base / "status.json"
            if status_file.exists():
                with open(status_file, "r") as f:
                    data = json.load(f)
                data["status"] = "uploaded"
                data["retry_count"] = data.get("retry_count", 0) + 1
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                with open(status_file, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Файл {file_id} подготовлен к повторной обработке")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка подготовки к повторной обработке {file_id}: {e}")
            return False

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        """Определяет MIME-тип по расширению."""
        mime_types = {
            ".pdf": "application/pdf", ".txt": "text/plain",
            ".json": "application/json", ".csv": "text/csv",
            ".xml": "application/xml", ".png": "image/png",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp",
        }
        return mime_types.get(path.suffix.lower(), "application/octet-stream")

    # ========================================================================
    # 🔹 НОВЫЕ МЕТОДЫ ДЛЯ FINGERPRINT И ЗАЩИТЫ ОТ ДУБЛИКАТОВ
    # ========================================================================

    def get_file_fingerprint(self, file_id: str, original_filename: str) -> Optional[str]:
        """
        Получает fingerprint для файла по его ID и имени.

        Args:
            file_id: ID файла
            original_filename: Оригинальное имя файла

        Returns:
            str: Fingerprint или None если файл не найден
        """
        file_path = get_safe_file_path(file_id, original_filename, self.base_dir)
        if file_path:
            return get_file_fingerprint(file_path)
        return None

    def is_duplicate_file(self, filepath: Path, redis_client: Any) -> bool:
        """
        Проверяет, является ли файл дубликатом уже обработанного.

        Args:
            filepath: Путь к файлу на диске
            redis_client: Redis клиент

        Returns:
            bool: True если файл уже обрабатывается/обработан
        """
        return is_file_already_processed(filepath, redis_client, self.base_dir)

    def save_fingerprint_to_job(self, job: "FileJob", filepath: Path) -> bool:
        """
        Сохраняет fingerprint файла в метаданные джоба.

        Args:
            job: Экземпляр FileJob
            filepath: Путь к файлу для вычисления fingerprint

        Returns:
            bool: True если успешно
        """
        fingerprint = get_file_fingerprint(filepath)
        if fingerprint:
            job.metadata["file_fingerprint"] = fingerprint
            return True
        return False

    def cleanup_orphaned_jobs(self, redis_client: Any, min_age_hours: int = 1) -> Dict[str, int]:
        """
        Обёртка над cleanup_orphaned_jobs из helpers.

        Args:
            redis_client: Redis клиент
            min_age_hours: Минимальный возраст джоба для очистки

        Returns:
            Dict со статистикой очистки
        """
        return cleanup_orphaned_jobs(
            redis_client=redis_client,
            base_dir=self.base_dir,
            min_age_hours=min_age_hours
        )