# workers/ocr/src/worker/ocr_worker.py
"""Worker для OCR модуля."""

import json
import time
import signal
import sys

import redis

from src.config import config
from src.logger import get_logger, logger_with_context
from src.models.file import FileJob
from src.modules.ocr import OCRModule

logger = get_logger(__name__)


class OCRWorker:
    """Worker для обработки OCR заданий."""

    def __init__(self):
        self.redis_client = None
        self.shutdown_requested = False
        self.module = OCRModule()
        self.queue_name = config.redis_queue
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"Получен сигнал {signum}, остановка...")
        self.shutdown_requested = True

    def connect(self) -> bool:
        try:
            self.redis_client = redis.Redis.from_url(config.redis_url)
            self.redis_client.ping()
            logger.info(f"Подключено к Redis: {config.redis_url}")
            logger.info(f"Доступные OCR движки: {self.module.get_available_engines()}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Ошибка подключения: {e}")
            return False

    def process_job(self, payload: str) -> bool:
        try:
            job = FileJob.from_payload(payload)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Неверный формат: {e}")
            return False

        job_logger = logger_with_context(
            logger,
            file_id=job.file_id,
            filename=job.original_filename,
            ocr_engine=job.ocr_engine
        )

        job_logger.info(f"Начало OCR обработки")

        success = self.module.process(job)

        if success:
            job.complete_module(self.module.name)
            job_logger.info(f"OCR модуль завершён успешно")
            job.status = "processing"
            self._update_job_status(job)
        else:
            job_logger.error(f"OCR модуль завершился с ошибкой")
            self._handle_error(job)

        return success

    def _update_job_status(self, job: FileJob):
        """Обновление статуса задания в Redis."""
        self.redis_client.publish(
            "files:events",
            json.dumps({
                "file_id": job.file_id,
                "event": "module_completed",
                "module": self.module.name,
                "status": job.status,
                "completed_modules": list(job.completed_modules)
            })
        )

    def _handle_error(self, job: FileJob):
        job.retry_count += 1
        if job.retry_count < job.max_retries:
            logger.info(f"Повторная попытка {job.retry_count}/{job.max_retries}")
            self.redis_client.rpush(self.queue_name, job.to_payload())
        else:
            logger.error(f"Максимум попыток исчерпан: {job.file_id}")
            job.status = "failed"
            self._update_job_status(job)

    def run(self):
        if not self.connect():
            sys.exit(1)

        logger.info(f"OCR Worker запущен, очередь: {self.queue_name}")

        error_count = 0

        while not self.shutdown_requested:
            try:
                item = self.redis_client.blpop(self.queue_name, timeout=config.redis_timeout)

                if not item:
                    continue

                _, payload = item
                success = self.process_job(payload)

                error_count = 0 if success else error_count + 1
                if error_count >= 10:
                    logger.critical("Слишком много ошибок, остановка")
                    break

            except redis.ConnectionError as e:
                logger.error(f"Потеряно соединение: {e}")
                time.sleep(5)
                if not self.connect():
                    break
            except Exception as e:
                logger.exception(f"Ошибка: {e}")
                error_count += 1
                time.sleep(min(2 ** error_count, 60))

        logger.info("OCR Worker остановлен")


def main():
    config.validate()
    worker = OCRWorker()
    worker.run()


if __name__ == "__main__":
    main()