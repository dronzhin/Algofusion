from __future__ import annotations

import json
import signal
import sys
import time

import redis

from src.config import config
from src.logger import get_logger, logger_with_context
from src.models.file import FileJob, FileStatus
from src.modules.final_json import FinalJsonModule

logger = get_logger(__name__)


class FinalJsonWorker:
    def __init__(self):
        self.redis_client = None
        self.shutdown_requested = False
        self.module = FinalJsonModule()
        self.queue_name = config.redis_queue
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

        job_logger = logger_with_context(logger, file_id=job.file_id, filename=job.original_filename)
        job_logger.info("Final JSON processing started")
        success = self.module.process(job)
        if success:
            job.complete_module(self.module.name)
            job.status = FileStatus.COMPLETED
            job.current_module = None
            self.redis_client.publish(
                "files:events",
                json.dumps(
                    {
                        "file_id": job.file_id,
                        "event": "module_completed",
                        "module": self.module.name,
                        "status": job.status.value,
                        "completed_modules": list(job.completed_modules),
                        "next_module": None,
                    },
                    ensure_ascii=False,
                ),
            )
            job_logger.info("Final JSON completed successfully")
        else:
            job_logger.error("Final JSON failed")
        return success

    def run(self) -> None:
        if not self.connect():
            sys.exit(1)
        logger.info("Final JSON worker started, queue: %s", self.queue_name)
        while not self.shutdown_requested:
            try:
                item = self.redis_client.blpop(self.queue_name, timeout=config.redis_timeout)
                if not item:
                    continue
                _, payload = item
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                self.process_job(payload)
            except redis.ConnectionError as exc:
                logger.error("Redis connection lost: %s", exc)
                time.sleep(5)
                if not self.connect():
                    break
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)
                time.sleep(5)

        logger.info("Final JSON worker stopped")


def main() -> None:
    config.validate()
    FinalJsonWorker().run()


if __name__ == "__main__":
    main()
