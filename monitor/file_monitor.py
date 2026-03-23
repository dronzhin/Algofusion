# monitor/file_monitor.py
"""
Мониторинг внешней папки для новых файлов.
Запускается как отдельный контейнер.
"""

import time
import shutil
import uuid
from pathlib import Path
from typing import Set
from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir
from core.services.redis_client import get_redis_client
from typing import Optional

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """Мониторит внешнюю папку и создаёт задания для новых файлов."""

    def __init__(
            self,
            external_path: Optional[str] = None,
            shared_path: Optional[str] = None,
            check_interval: Optional[int] = None
    ):
        settings = get_settings()

        self.external_path = Path(external_path or settings.external_monitor_path)
        self.shared_path = Path(shared_path or settings.shared_files_path)
        self.check_interval = check_interval or settings.monitor_interval
        self.processed_files: Set[str] = set()
        self.redis = get_redis_client()

        logger.info(
            f"FileMonitor инициализирован: "
            f"external={self.external_path}, "
            f"shared={self.shared_path}, "
            f"interval={self.check_interval}s"
        )

    def start(self):
        """Запуск цикла мониторинга."""
        logger.info(f"Запуск мониторинга папки {self.external_path}")
        safe_mkdir(self.external_path)
        safe_mkdir(self.shared_path)

        while True:
            try:
                self.check_for_new_files()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}", exc_info=True)
                time.sleep(self.check_interval)

    def check_for_new_files(self):
        """Проверка новых файлов во внешней папке."""
        if not self.external_path.exists():
            logger.warning(f"Внешняя папка не существует: {self.external_path}")
            return

        for item in self.external_path.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                # Уникальный ключ для отслеживания
                file_stat = item.stat()
                cache_key = f"{item.name}:{file_stat.st_mtime}:{file_stat.st_size}"

                if cache_key not in self.processed_files:
                    logger.info(f"Обнаружен новый файл: {item.name}")
                    file_id = str(uuid.uuid4())[:8]
                    self.process_new_file(item, file_id)
                    self.processed_files.add(cache_key)

                    # Очищаем старые записи (держим последние 1000)
                    if len(self.processed_files) > 1000:
                        self.processed_files = set(list(self.processed_files)[-1000:])

    def process_new_file(self, file_path: Path, file_id: str):
        """Обработка нового файла: создание структуры и отправка в очередь."""
        try:
            # Создаём структуру папок
            base_dir = self.shared_path / file_id
            original_dir = base_dir / "original"
            safe_mkdir(original_dir)

            # Копируем файл
            dest_path = original_dir / file_path.name
            shutil.copy2(file_path, dest_path)
            logger.info(f"Файл скопирован: {file_path} → {dest_path}")

            # Создаём FileJob
            file_type = FileJob.detect_file_type(file_path.name)
            file_size = file_path.stat().st_size

            job = FileJob(
                file_id=file_id,
                original_filename=file_path.name,
                file_type=file_type,
                file_size=file_size,
                status=FileStatus.UPLOADED,
                current_module="preprocess",
                export_to_1c=True
            )

            # Сохраняем статус в Redis
            self.redis.set_file_status(file_id, job.to_dict())

            # Отправляем в очередь preprocess
            self.redis.push_to_queue("files:preprocess", job.to_payload(), priority=job.priority)

            # Публикуем событие для UI
            self.redis.publish_event("files:events", {
                "type": "file_uploaded",
                "file_id": file_id,
                "filename": file_path.name,
                "status": job.status.value,
                "file_type": file_type.value,
                "file_size": file_size
            })

            logger.info(f"Файл {file_id} добавлен в очередь обработки")

        except Exception as e:
            logger.error(f"Ошибка обработки файла {file_path}: {e}", exc_info=True)
            self.redis.publish_event("files:events", {
                "type": "file_error",
                "filename": file_path.name,
                "error": str(e)
            })


def main():
    """Точка входа для контейнера monitor."""
    logger.info("Запуск FileMonitor...")

    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()