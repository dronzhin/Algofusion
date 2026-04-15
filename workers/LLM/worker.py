#!/usr/bin/env python3
# workers/LLM/worker.py
"""
Worker для LLM-обработки с идемпотентностью и защитой от повторов.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

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
    CONFIG_CHANNEL = "config:llm:updates"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.redis = get_redis_client()
        self.file_service = FileService(base_dir=self.settings.shared_files_path)
        self.config = LLMProcessingConfig()
        self.processor = LLMProcessor(config=self.config, redis_client=self.redis)

        self.queues = [FileJob.get_queue_for_module("llm")]
        self.delayed_queue_key = "files:llm:delayed"

        self._config_pubsub = None
        self._last_config_update = 0.0
        self._config_update_interval = 1.0
        logger.info("LLMWorker инициализирован")

    def _subscribe_to_config_updates(self):
        try:
            self._config_pubsub = self.redis.subscribe([self.CONFIG_CHANNEL])
            logger.info(f"✅ Подписка на конфигурацию: {self.CONFIG_CHANNEL}")
        except Exception as e:
            logger.error(f"❌ Ошибка подписки: {e}")

    def _check_config_updates(self):
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
            if event.get("type") == "settings_updated":
                self._apply_config_update(event.get("settings", {}))
        except Exception as e:
            logger.debug(f"⚠️ Ошибка проверки конфига: {e}")

    def _apply_config_update(self, new_settings: Dict[str, Any]):
        updated = False
        if "llm_classifier_model" in new_settings and new_settings["llm_classifier_model"] != self.config.classifier_model:
            self.config.classifier_model = new_settings["llm_classifier_model"]
            updated = True
        if "llm_extractor_model" in new_settings and new_settings["llm_extractor_model"] != self.config.extractor_model:
            self.config.extractor_model = new_settings["llm_extractor_model"]
            updated = True
        if "llm_temperature" in new_settings:
            self.config.temperature = float(new_settings["llm_temperature"])
            updated = True
        if "llm_max_tokens" in new_settings:
            self.config.max_tokens = int(new_settings["llm_max_tokens"])
            updated = True

        if updated:
            try:
                self.processor = LLMProcessor(config=self.config, redis_client=self.redis)
                logger.info("✅ LLMProcessor обновлён")
            except Exception as e:
                logger.error(f"❌ Ошибка обновления процессора: {e}")

    def _push_delayed(self, payload: str, delay_sec: int, priority: int = 0):
        execute_at = time.time() + delay_sec
        member = f"{priority}:{payload}"
        try:
            self.redis.client.zadd(self.delayed_queue_key, {member: execute_at})
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в отложенную очередь: {e}")

    def _process_delayed_queue(self) -> Tuple[Optional[str], int]:
        try:
            result = self.redis.client.zpopmin(self.delayed_queue_key, count=1)
            if not result:
                return None, 0
            member, score = result[0]
            if isinstance(member, (bytes, bytearray)):
                member = member.decode("utf-8")
            if ":" not in member:
                return None, 0
            priority_str, payload = member.split(":", 1)
            priority = int(priority_str) if priority_str.isdigit() else 0
            return payload, priority
        except Exception as e:
            logger.error(f"❌ Ошибка обработки отложенной очереди: {e}")
            return None, 0

    def _process_single_job(self, payload: str, priority: int = 0) -> bool:
        job, error = FileJob.from_payload_safe(payload)
        if job is None:
            logger.error(f"❌ Не удалось распарсить задание: {error}")
            return False

        # 🔹 ИДЕМПОТЕНТНОСТЬ: Если LLM уже отработал, пропускаем
        if "llm" in job.completed_modules:
            logger.info(f"⏭️ Пропуск: {job.file_id} уже обработан модулем LLM")
            return True

        # 🔹 Проверка финальных статусов в Redis (защита от гонок)
        try:
            latest_status = self.redis.get_file_status(job.file_id)
            if latest_status and latest_status.get("status") in [FileStatus.COMPLETED.value, FileStatus.FAILED.value]:
                logger.info(f"🛑 Пропуск: {job.file_id} имеет финальный статус {latest_status['status']}")
                return True
        except Exception:
            pass

        try:
            logger.info(f"🎯 LLM задание: {job.file_id} ({job.original_filename})")
            self._check_config_updates()

            if hasattr(job, 'llm_classifier_model') and job.llm_classifier_model:
                self.config.classifier_model = job.llm_classifier_model
            if hasattr(job, 'llm_extractor_model') and job.llm_extractor_model:
                self.config.extractor_model = job.llm_extractor_model

            job.status = FileStatus.PROCESSING
            job.current_module = "llm"
            job.updated_at = datetime.now(timezone.utc)
            self.redis.set_file_status(job.file_id, job.to_dict())

            FileJob.publish_event(self.redis, FileJob.build_status_changed_event(
                file_id=job.file_id, status=job.status.value,
                current_module=job.current_module, completed_modules=list(job.completed_modules),
                filename=job.original_filename
            ))

            result_path = self.processor.process(job=job, file_service=self.file_service)

            if result_path:
                job.completed_modules.add("llm")
                job.current_module = None
                job.updated_at = datetime.now(timezone.utc)
                logger.info(f"✅ LLM обработка завершена: {result_path.name}")

                allowed = job.get_allowed_modules()
                if "export" in allowed and "export" not in job.completed_modules:
                    job.current_module = "export"
                    job.metadata["llm_json_path"] = str(result_path.relative_to(self.file_service.base_dir))
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    self.redis.push_to_queue(FileJob.QUEUE_EXPORT, job.to_payload(), priority=job.priority)
                else:
                    job.status = FileStatus.COMPLETED
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    FileJob.publish_event(self.redis, FileJob.build_status_changed_event(
                        file_id=job.file_id, status=FileStatus.COMPLETED.value,
                        completed_modules=list(job.completed_modules), filename=job.original_filename
                    ))
                return True

            elif result_path is None and job.classification_pending:
                attempts = job.metadata.get("pending_requeue_attempts", 0) + 1
                if attempts >= self.config.max_pending_requeues:
                    job.status = FileStatus.FAILED
                    job.errors.append("Classification pending timeout")
                    self.redis.set_file_status(job.file_id, job.to_dict())
                    return False

                job.metadata["pending_requeue_attempts"] = attempts
                job.metadata["last_pending_at"] = datetime.now(timezone.utc).isoformat()
                self.redis.set_file_status(job.file_id, job.to_dict())
                delay = min(self.config.pending_recheck_delay_sec * (1 + attempts * 0.5), 300)
                logger.info(f"🔄 {job.file_id} в отложенной очереди на {delay:.0f}с")
                self._push_delayed(job.to_payload(), delay, priority=job.priority)
                return True

        except LLMProcessingError as e:
            logger.error(f"❌ Ошибка LLM: {e}")
            self._fail_job(job, str(e))
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}", exc_info=True)
            self._fail_job(job, f"Unexpected: {e}")

        return False

    def _fail_job(self, job: FileJob, error_msg: str):
        job.status = FileStatus.FAILED
        job.errors.append(error_msg)
        job.updated_at = datetime.now(timezone.utc)
        self.redis.set_file_status(job.file_id, job.to_dict())
        FileJob.publish_event(self.redis, FileJob.build_status_changed_event(
            file_id=job.file_id, status=FileStatus.FAILED.value,
            error=error_msg, exception_type="LLMProcessingError", filename=job.original_filename
        ))

    def run(self, poll_interval: float = 1.0):
        logger.info("🚀 Запуск LLM worker'а...")
        self._subscribe_to_config_updates()

        while True:
            try:
                self._check_config_updates()
                payload, priority = self._process_delayed_queue()
                if not payload:
                    for queue in self.queues:
                        payload = self.redis.pop_from_queue(queue, timeout=0)
                        if payload:
                            priority = 0
                            break

                if payload:
                    self._process_single_job(payload, priority)
                    time.sleep(0.2)

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле: {e}", exc_info=True)
                time.sleep(poll_interval)

        if self._config_pubsub:
            self._config_pubsub.close()
        self.redis.close()
        logger.info("👋 Завершение")

def main():
    try:
        settings = get_settings()
        worker = LLMWorker(settings=settings)
        worker.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()