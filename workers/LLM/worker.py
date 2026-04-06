#!/usr/bin/env python3

# workers/LLM/worker.py
"""
Worker для LLM-обработки.
Слушает очередь Redis и выполняет пайплайн.
Аналогично workers/OCR/worker.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Добавляем корень проекта для импортов
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings, Settings
from shared.utils.logger import setup_logger
from core.services.redis_client import get_redis_client
from core.services.file_service import FileService
from workers.LLM.src.config import LLMProcessingConfig
from workers.LLM.src.services.llm_processor import LLMProcessor, LLMProcessingError

logger = setup_logger("workers.llm.worker")


class LLMWorker:
    """Worker для LLM-обработки из очереди Redis."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

        self.redis = get_redis_client()
        self.file_service = FileService(base_dir=self.settings.shared_files_path)

        # Конфигурация и процессор
        llm_config = LLMProcessingConfig()
        self.processor = LLMProcessor(config=llm_config, redis_client=self.redis)

        self.queues = FileJob.get_queue_for_module("llm")

        logger.info(f"LLMWorker инициализирован")
        logger.info(f"📁 Shared path: {self.settings.shared_files_path}")
        logger.info(f"🔗 Redis: {self.settings.redis_host}:{self.settings.redis_port}")
        logger.info(f"🤖 Ollama: {llm_config.ollama_endpoint}/{llm_config.ollama_model}")

    def _process_single_job(self, payload: str) -> bool:
        """Обрабатывает одно задание из очереди."""

        # ====================================================================
        # ЭТАП 1: Парсинг задания
        # ====================================================================
        job, error = FileJob.from_payload_safe(payload)

        if job is None:
            logger.error(f"❌ Не удалось распарсить задание: {error}")
            event = FileJob.build_processing_error_event(
                file_id="unknown",
                error=error,
                module="llm",
                exception_type="ParseError"
            )
            FileJob.publish_event(self.redis, event)
            return False

        # ====================================================================
        # ЭТАП 2: Обработка задания
        # ====================================================================
        try:
            logger.info(f"🎯 LLM задание: {job.file_id} ({job.original_filename})")

            # Обновляем статус
            job.status = FileStatus.PROCESSING
            job.current_module = "llm"
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            event = FileJob.build_status_changed_event(
                file_id=job.file_id,
                status=job.status.value,
                current_module=job.current_module,
                completed_modules=list(job.completed_modules),
                filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)

            # ====================================================================
            # ВЫПОЛНЕНИЕ ОБРАБОТКИ
            # ====================================================================
            result_path = self.processor.process(
                job=job,
                file_service=self.file_service
            )

            # 🔹 Проверка успеха
            if result_path:
                # ✅ Успех
                job.completed_modules.add("llm")
                job.current_module = None
                job.updated_at = datetime.now(timezone.utc)

                logger.info(f"✅ LLM обработка завершена: {result_path.name}")

                # Отправляем в следующую очередь если нужно
                allowed = job.get_allowed_modules()
                if "export" in allowed and "export" not in job.completed_modules:
                    job.current_module = "export"
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    self.redis.push_to_queue("files:export", job.to_payload(), priority=job.priority)
                    logger.info(f"📤 В очередь export: {job.file_id}")
                else:
                    # Обработка завершена
                    job.status = FileStatus.COMPLETED
                    self.redis.set_file_status(job.file_id, job.to_dict())

                    event = FileJob.build_status_changed_event(
                        file_id=job.file_id,
                        status=FileStatus.COMPLETED.value,
                        completed_modules=list(job.completed_modules),
                        filename=job.original_filename,
                    )
                    FileJob.publish_event(self.redis, event)
                    logger.info(f"✅ Завершено: {job.file_id}")

                return True
            else:
                raise LLMProcessingError("Результат LLM пуст")

        except LLMProcessingError as e:
            logger.error(f"❌ Ошибка LLM: {e}")
            job.status = FileStatus.FAILED
            job.errors.append(str(e))
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            event = FileJob.build_status_changed_event(
                file_id=job.file_id,
                status=FileStatus.FAILED.value,
                error=str(e),
                current_module=job.current_module,
                filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)
            return False

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}", exc_info=True)
            job.status = FileStatus.FAILED
            job.errors.append(f"Unexpected: {e}")
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            event = FileJob.build_status_changed_event(
                file_id=job.file_id,
                status=FileStatus.FAILED.value,
                error=f"Unexpected: {e}",
                exception_type=type(e).__name__,
                filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)
            return False

    def run(self, poll_interval: float = 1.0):
        """Запуск цикла прослушивания."""
        logger.info("🚀 Запуск LLM worker'а...")

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
    logger.info("🔧 Запуск LLM worker'а...")

    try:
        settings = get_settings()
        worker = LLMWorker(settings=settings)
        worker.run()

    except KeyboardInterrupt:
        logger.info("🛑 Остановлен пользователем (Ctrl+C)")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        logger.error("🔧 Проверьте логи выше для деталей")
        sys.exit(1)


if __name__ == "__main__":
    main()