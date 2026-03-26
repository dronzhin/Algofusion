from __future__ import annotations

import json
import signal
import sys
import time

import redis

from src.config import config
from src.logger import get_logger, logger_with_context
from src.models.file import FileJob, FileStatus
from src.modules.ocr import OCRModule

logger = get_logger(__name__)


class OCRWorker:
    def __init__(self):
        self.redis_client = None
        self.shutdown_requested = False
        self.module = OCRModule()
        self.queue_name = config.redis_queue
        self.next_queue = config.next_queue
        self._setup_signals()

    def _setup_signals(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        logger.info("Received signal %s, shutting down", signum)
        self.shutdown_requested = True

    def connect(self) -> bool:
        try:
            self.redis_client = redis.Redis.from_url(config.redis_url)
            self.redis_client.ping()
            logger.info("Connected to Redis: %s", config.redis_url)
            return True
        except redis.ConnectionError as exc:
            logger.error("Redis connection error: %s", exc)
            return False

    def process_job(self, payload: str) -> bool:
        try:
            job = FileJob.from_payload(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Invalid payload: %s", exc)
            return False

        job_logger = logger_with_context(
            logger,
            file_id=job.file_id,
            filename=job.original_filename,
        )
        job_logger.info("OCR processing started")

        success = self.module.process(job)
        if success:
            job.complete_module(self.module.name)
            job.status = FileStatus.PROCESSING
            job.current_module = "parser"
            self._enqueue_next(job)
            self._publish_status(job)
            job_logger.info("OCR completed successfully")
        else:
            job_logger.error("OCR failed")
            self._handle_error(job)
        return success

    def _enqueue_next(self, job: FileJob) -> None:
        self.redis_client.rpush(self.next_queue, job.to_payload())

    def _publish_status(self, job: FileJob) -> None:
        self.redis_client.publish(
            "files:events",
            json.dumps(
                {
                    "file_id": job.file_id,
                    "event": "module_completed",
                    "module": self.module.name,
                    "status": job.status.value,
                    "completed_modules": list(job.completed_modules),
                    "next_module": job.current_module,
                },
                ensure_ascii=False,
            ),
        )

    def _handle_error(self, job: FileJob) -> None:
        job.retry_count += 1
        if job.retry_count < min(job.max_retries, config.max_retries):
            logger.info("Retry %s/%s", job.retry_count, job.max_retries)
            self.redis_client.rpush(self.queue_name, job.to_payload())
        else:
            logger.error("Retry limit reached: %s", job.file_id)
            job.status = FileStatus.FAILED
            self._publish_status(job)

    def run(self) -> None:
        if not self.connect():
            sys.exit(1)

        logger.info("OCR worker started, queue: %s", self.queue_name)
        error_count = 0

        while not self.shutdown_requested:
            try:
                item = self.redis_client.blpop(self.queue_name, timeout=config.redis_timeout)
                if not item:
                    continue

                _, payload = item
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                success = self.process_job(payload)
                error_count = 0 if success else error_count + 1
                if error_count >= 10:
                    logger.critical("Too many errors, stopping worker")
                    break
            except redis.ConnectionError as exc:
                logger.error("Redis connection lost: %s", exc)
                time.sleep(5)
                if not self.connect():
                    break
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)
                error_count += 1
                time.sleep(min(2 ** error_count, 60))

        logger.info("OCR worker stopped")


def main() -> None:
    config.validate()
    worker = OCRWorker()
    worker.run()


if __name__ == "__main__":
    main()
