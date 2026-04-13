#!/usr/bin/env python3
# workers/OCR/worker.py
"""
Worker для OCR-обработки с поддержкой мгновенного обновления настроек.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings, Settings
from shared.utils.logger import setup_logger
from core.services.redis_client import get_redis_client
from core.services.file_service import FileService
from workers.OCR.src.config import OCRProcessingConfig
from workers.OCR.src.services.ocr_processor import OCRProcessor, OCRProcessingError

logger = setup_logger("workers.ocr.worker")


class OCRWorker:
    """Worker для OCR-обработки с live-reload настроек."""

    CONFIG_CHANNEL = "config:ocr:updates"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.redis = get_redis_client()
        self.file_service = FileService(base_dir=self.settings.shared_files_path)

        self.config = OCRProcessingConfig()
        self.processor = OCRProcessor(config=self.config)

        self.queues = [FileJob.get_queue_for_module("ocr")]

        # 🔹 Pub/Sub для конфигурации
        self._config_pubsub = None
        self._last_config_update = 0.0
        self._config_update_interval = 1.0

        logger.info(f"OCRWorker инициализирован")
        logger.info(f"📁 Shared path: {self.settings.shared_files_path}")
        logger.info(f"🔗 Redis: {self.settings.redis_host}:{self.settings.redis_port}")
        logger.info(f"🔤 OCR движок: {self.config.default_engine}")

    def _subscribe_to_config_updates(self):
        """Подписка на канал обновлений конфигурации."""
        try:
            self._config_pubsub = self.redis.subscribe([self.CONFIG_CHANNEL])
            logger.info(f"✅ Подписка на конфигурацию: {self.CONFIG_CHANNEL}")
        except Exception as e:
            logger.error(f"❌ Ошибка подписки на конфигурацию: {e}")

    def _check_config_updates(self):
        """Проверяет и применяет обновления конфигурации."""
        if self._config_pubsub is None:
            return

        now = time.time()
        if now - self._last_config_update < self._config_update_interval:
            return
        self._last_config_update = now

        try:
            message = self._config_pubsub.get_message(timeout=0.01)
            if not message or message.get("type") != "message":
                return

            event = json.loads(message["data"])
            if event.get("type") != "settings_updated":
                return

            self._apply_config_update(event.get("settings", {}))

        except Exception as e:
            logger.debug(f"⚠️ Ошибка проверки конфигурации: {e}")

    def _apply_config_update(self, new_settings: Dict[str, Any]):
        """Применяет новые настройки к воркеру."""
        updated = False

        # 🔹 Обновление движка OCR
        if "ocr_engine" in new_settings and new_settings["ocr_engine"] != self.config.default_engine:
            old = self.config.default_engine
            self.config.default_engine = new_settings["ocr_engine"]
            logger.info(f"🔄 OCR движок: {old} → {self.config.default_engine}")
            updated = True

        # 🔹 Обновление языков
        if "ocr_langs" in new_settings:
            langs = new_settings["ocr_langs"]
            if isinstance(langs, list):
                langs = "+".join(langs)
            if langs != self.config.default_lang:
                self.config.default_lang = langs
                logger.info(f"🔄 Языки OCR: {self.config.default_lang}")
                updated = True

        # 🔹 Обновление параметров Tesseract
        if "tesseract_oem" in new_settings:
            self.config.tesseract_oem = int(new_settings["tesseract_oem"])
            updated = True
        if "tesseract_psm" in new_settings:
            self.config.tesseract_psm = int(new_settings["tesseract_psm"])
            updated = True
        if "tesseract_preprocess" in new_settings:
            self.config.tesseract_preprocess = bool(new_settings["tesseract_preprocess"])
            updated = True

        # 🔹 Пересоздание процессора при изменении движка
        if updated:
            logger.info("🔄 Пересоздание OCRProcessor с новыми настройками...")
            try:
                self.processor = OCRProcessor(config=self.config)
                logger.info("✅ OCRProcessor обновлён")
            except Exception as e:
                logger.error(f"❌ Ошибка обновления процессора: {e}")

    def _process_single_job(self, payload: str) -> bool:
        job, error = FileJob.from_payload_safe(payload)
        if job is None:
            logger.error(f"❌ Не удалось распарсить задание: {error}")
            event = FileJob.build_processing_error_event(
                file_id="unknown", error=error, module="ocr", exception_type="ParseError"
            )
            FileJob.publish_event(self.redis, event)
            return False

        try:
            logger.info(f"🎯 OCR задание: {job.file_id} ({job.original_filename})")

            # 🔹 Проверяем обновления конфига
            self._check_config_updates()

            # Применяем настройки из задания (приоритет)
            if hasattr(job, 'ocr_engine') and job.ocr_engine:
                self.config.default_engine = job.ocr_engine
            if hasattr(job, 'ocr_langs') and job.ocr_langs:
                langs = job.ocr_langs
                if isinstance(langs, list):
                    langs = "+".join(langs)
                self.config.default_lang = langs

            job.status = FileStatus.PROCESSING
            job.current_module = "ocr"
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            event = FileJob.build_status_changed_event(
                file_id=job.file_id, status=job.status.value,
                current_module=job.current_module, completed_modules=list(job.completed_modules),
                filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)

            result_paths: List[Path] = self.processor.process(job=job, file_service=self.file_service)

            if result_paths:
                job.completed_modules.add("ocr")
                job.current_module = None
                job.updated_at = datetime.now(timezone.utc)
                logger.info(f"✅ Распознано страниц: {len(result_paths)}")

                allowed = job.get_allowed_modules()
                if "llm" in allowed and "llm" not in job.completed_modules:
                    job.current_module = "llm"
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    self.redis.push_to_queue(FileJob.get_queue_for_module("llm"), job.to_payload(), priority=job.priority)
                    logger.info(f"📤 В очередь LLM: {job.file_id}")
                else:
                    job.status = FileStatus.COMPLETED
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    event = FileJob.build_status_changed_event(
                        file_id=job.file_id, status=FileStatus.COMPLETED.value,
                        completed_modules=list(job.completed_modules),
                        filename=job.original_filename, page_count=len(result_paths),
                    )
                    FileJob.publish_event(self.redis, event)
                    logger.info(f"✅ Завершено: {job.file_id}")
                return True
            else:
                raise OCRProcessingError("Результат OCR пуст")

        except OCRProcessingError as e:
            logger.error(f"❌ Ошибка OCR: {e}")
            job.status = FileStatus.FAILED
            job.errors.append(str(e))
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())
            event = FileJob.build_status_changed_event(
                file_id=job.file_id, status=FileStatus.FAILED.value,
                error=str(e), current_module=job.current_module, filename=job.original_filename
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
                file_id=job.file_id, status=FileStatus.FAILED.value,
                error=f"Unexpected: {e}", exception_type=type(e).__name__, filename=job.original_filename
            )
            FileJob.publish_event(self.redis, event)
            return False

        return False

    def run(self, poll_interval: float = 1.0):
        logger.info("🚀 Запуск OCR worker'а...")

        # 🔹 Подписка на конфигурацию
        self._subscribe_to_config_updates()

        while True:
            try:
                # 🔹 Проверка обновлений в каждом цикле
                self._check_config_updates()

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

        if self._config_pubsub:
            self._config_pubsub.close()
        self.redis.close()
        logger.info("👋 Завершение")


def main():
    logger.info("🔧 Запуск OCR worker'а...")
    try:
        settings = get_settings()
        worker = OCRWorker(settings=settings)
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