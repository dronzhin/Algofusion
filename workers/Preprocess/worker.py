#!/usr/bin/env python3

# workers/Preprocess/worker.py
"""
Worker для обработки изображений.
Слушает очередь Redis и выполняет пайплайн.
Все страницы обрабатываются в памяти.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

# Добавляем корень проекта для импортов
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings, Settings
from shared.utils.logger import setup_logger
from core.services.redis_client import get_redis_client
from core.services.file_service import FileService
from workers.Preprocess.src.config import ImageProcessingConfig
from workers.Preprocess.src.services.image_processor import ImageProcessor, ImageProcessingError

logger = setup_logger("workers.Preprocess.worker")


class ImageProcessorWorker:
    """Worker для обработки изображений из очереди Redis."""

    def __init__(self, settings: Optional[Settings] = None):
        # 🔹 Если settings не передан — получаем через get_settings()
        self.settings = settings or get_settings()

        self.redis = get_redis_client()
        self.file_service = FileService(base_dir=self.settings.shared_files_path)

        # 🔹 Передаём конфигурацию в процессор
        processor_config = ImageProcessingConfig()
        self.processor = ImageProcessor(config=processor_config)

        self.queues = [FileJob.get_queue_for_module("preprocess")]

        logger.info(f"ImageProcessorWorker инициализирован")
        logger.info(f"📁 Shared path: {self.settings.shared_files_path}")
        logger.info(f"🔗 Redis: {self.settings.redis_host}:{self.settings.redis_port}")

    def _process_single_job(self, payload: str) -> bool:
        """Обрабатывает одно задание из очереди."""

        # ====================================================================
        # ЭТАП 1: Парсинг задания
        # ====================================================================
        job, error = FileJob.from_payload_safe(payload)

        if job is None:
            logger.error(f"❌ Не удалось распарсить задание: {error}")

            # 🔹 Публикация ошибки через билдер + хелпер публикации
            event = FileJob.build_processing_error_event(
                file_id="unknown",
                error=error,
                module="preprocess",
                exception_type="ParseError"
            )
            FileJob.publish_event(self.redis, event)
            return False

        # ====================================================================
        # ЭТАП 2: Обработка задания
        # ====================================================================
        try:
            logger.info(f"🎯 Задание: {job.file_id} ({job.original_filename})")

            # Обновляем статус в Redis
            job.status = FileStatus.PROCESSING
            job.current_module = "preprocess"
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            # 🔹 Публикуем событие через билдер + хелпер
            event = FileJob.build_status_changed_event(
                file_id=job.file_id,
                status=job.status.value,
                current_module=job.current_module,
                completed_modules=list(job.completed_modules),
                filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)

            # ====================================================================
            # ВЫПОЛНЕНИЕ ОБРАБОТКИ (все страницы в памяти)
            # ====================================================================
            # 🔹 process() возвращает List[Path] — пути ко всем обработанным страницам
            result_paths: List[Path] = self.processor.process(
                job=job,
                file_service=self.file_service
            )

            # 🔹 Проверка успеха: список не пустой
            if result_paths:
                # ✅ Успех
                job.completed_modules.add("preprocess")
                job.current_module = None
                job.updated_at = datetime.now(timezone.utc)

                logger.info(f"✅ Обработано страниц: {len(result_paths)}")

                # Отправляем в следующую очередь если нужно
                allowed = job.get_allowed_modules()
                if "ocr" in allowed and "ocr" not in job.completed_modules:
                    job.current_module = "ocr"
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    self.redis.push_to_queue(FileJob.get_queue_for_module("ocr"), job.to_payload(), priority=job.priority)
                    logger.info(f"📤 В очередь OCR: {job.file_id}")
                else:
                    # Обработка завершена
                    job.status = FileStatus.COMPLETED
                    self.redis.set_file_status(job.file_id, job.to_dict())

                    # 🔹 Публикуем событие о завершении
                    event = FileJob.build_status_changed_event(
                        file_id=job.file_id,
                        status=FileStatus.COMPLETED.value,
                        completed_modules=list(job.completed_modules),
                        filename=job.original_filename,
                        page_count=len(result_paths),
                    )
                    FileJob.publish_event(self.redis, event)
                    logger.info(f"✅ Завершено: {job.file_id}")

                return True
            else:
                raise ImageProcessingError("Результат обработки пуст")

        except ImageProcessingError as e:
            logger.error(f"❌ Ошибка обработки: {e}")
            job.status = FileStatus.FAILED
            job.errors.append(str(e))
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            # 🔹 Публикуем событие об ошибке
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

            # 🔹 Публикуем событие с деталями исключения
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
    logger.info("🔧 Запуск воркера обработки изображений...")

    try:
        # 🔹 Получаем и валидируем настройки
        settings = get_settings()

        # 🔹 Инициализация и запуск воркера
        worker = ImageProcessorWorker(settings=settings)
        worker.run()

    except KeyboardInterrupt:
        logger.info("🛑 Воркер остановлен пользователем (Ctrl+C)")
        sys.exit(0)

    except SystemExit:
        raise

    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        logger.error("🔧 Проверьте логи выше для деталей")
        sys.exit(1)


if __name__ == "__main__":
    main()