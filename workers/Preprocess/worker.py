#!/usr/bin/env python3

# workers/Preprocess/worker.py
"""
Worker для обработки изображений.
Слушает очередь Redis и выполняет пайплайн.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Добавляем корень проекта для импортов
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from core.services.redis_client import get_redis_client
from core.services.file_service import FileService
from workers.Preprocess.src.services.image_processor import ImageProcessor, ImageProcessingError

logger = setup_logger("processor.worker")


class ImageProcessorWorker:
    """Worker для обработки изображений из очереди Redis."""

    def __init__(self):
        self.settings = get_settings()
        self.redis = get_redis_client()
        self.file_service = FileService(base_dir=self.settings.shared_files_path)
        self.processor = ImageProcessor()
        self.queues = ["files:preprocess"]

        logger.info(f"ImageProcessorWorker инициализирован")

    def _update_job_status(self, job: FileJob, status: FileStatus, error: str = None):
        """Обновляет статус в Redis и публикует событие."""
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if error:
            job.errors.append(error)

        self.redis.set_file_status(job.file_id, job.to_dict())

        event = {
            "type": "file_status_changed",
            "file_id": job.file_id,
            "status": status.value,
            "current_module": job.current_module,
            "completed_modules": list(job.completed_modules),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.redis.publish_event("files:events", event)

        logger.info(f"📊 Статус обновлён: {job.file_id} → {status.value}")

    def _process_single_job(self, payload: str) -> bool:
        """Обрабатывает одно задание."""
        try:
            job = FileJob.from_payload(payload)
            logger.info(f"🎯 Задание: {job.file_id} ({job.original_filename})")

            job.status = FileStatus.PROCESSING
            job.current_module = "preprocess"
            self._update_job_status(job, FileStatus.PROCESSING)

            result_path = self.processor.process_file_job(
                job=job,
                file_service=self.file_service,
                cleanup_temp=True
            )

            if result_path and result_path.exists():
                job.completed_modules.add("preprocess")
                job.current_module = None

                # Отправляем в следующую очередь если нужно
                allowed = job.get_allowed_modules()
                if "ocr" in allowed and "ocr" not in job.completed_modules:
                    job.current_module = "ocr"
                    self.redis.push_to_queue("files:ocr", job.to_payload(), priority=job.priority)
                    logger.info(f"📤 В очередь OCR: {job.file_id}")
                else:
                    job.status = FileStatus.COMPLETED
                    self._update_job_status(job, FileStatus.COMPLETED)
                    logger.info(f"✅ Завершено: {job.file_id}")

                return True
            else:
                raise ImageProcessingError("Результат не создан")

        except ImageProcessingError as e:
            logger.error(f"❌ Ошибка: {e}")
            self._update_job_status(job, FileStatus.FAILED, error=str(e))
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}", exc_info=True)
            self._update_job_status(job, FileStatus.FAILED, error=f"Unexpected: {e}")
            return False

    def run(self, poll_interval: float = 1.0):
        """Запуск цикла прослушивания."""
        logger.info("🚀 Запуск worker'а...")

        while True:
            try:
                for queue in self.queues:
                    payload = self.redis.pop_from_queue(queue, timeout=0)
                    if payload:
                        logger.info(f"📥 Из очереди {queue}")
                        self._process_single_job(payload)
                        time.sleep(0.5)
                        break
                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info("🛑 Остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле: {e}", exc_info=True)
                time.sleep(poll_interval)

        self.redis.close()
        logger.info("👋 Завершение")


def main():
    """Точка входа для Docker."""
    logger.info("🔧 Image Processor Worker starting...")

    required = ["REDIS_HOST", "SHARED_FILES_PATH"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"❌ Missing env vars: {missing}")
        sys.exit(1)

    try:
        worker = ImageProcessorWorker()
        worker.run()
    except Exception as e:
        logger.error(f"💥 Critical: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()