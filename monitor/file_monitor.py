# monitor/file_monitor.py
"""
Мониторинг внешней папки + автоматическое восстановление зависших джобов.
🔹 При старте: сразу проверяет Redis и возобновляет обработку.
🔹 Проверяет ТОЛЬКО оригинальный файл. Промежуточные файлы воркеры перегенерируют.
"""

import time
import shutil
import uuid
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from shared.models.file import FileJob, FileStatus
from shared.models.file.enums import FileType
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import (
    safe_mkdir,
    get_file_fingerprint,
    is_file_already_processed_by_fingerprint,
    update_fingerprint_index,
    validate_file_exists,
    FILE_FINGERPRINT_INDEX
)
from core.services.redis_client import get_redis_client

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """
    Мониторит внешнюю папку и восстанавливает зависшие джобы.
    🔹 Recovery запускается сразу при старте, затем каждые 60 секунд.
    """

    MIN_FILE_SIZE = 1024  # 1 KB
    FILE_STABLE_TIME = 2  # секунды стабильности файла
    INCOMING_CHECK_INTERVAL = 5
    RECOVERY_CHECK_INTERVAL = 60
    RECOVERY_GRACE_PERIOD_MINUTES = 2

    def __init__(
            self,
            external_path: Optional[str] = None,
            shared_path: Optional[str] = None,
            check_interval: Optional[int] = None
    ):
        settings = get_settings()
        self.external_path = Path(external_path or settings.external_monitor_path)
        self.shared_path = Path(shared_path or settings.shared_files_path)
        self.incoming_interval = check_interval or self.INCOMING_CHECK_INTERVAL
        self.redis = get_redis_client()
        self._file_cache: dict[str, tuple[float, float, int]] = {}
        self._last_incoming_check = 0.0
        self._last_recovery_check = 0.0
        self.module_queues = {
            "preprocess": "files:preprocess",
            "ocr": "files:ocr",
            "llm": "files:llm",
            "export": "files:export"
        }
        logger.info(
            f"FileMonitor инициализирован: "
            f"external={self.external_path}, "
            f"shared={self.shared_path}, "
            f"incoming={self.incoming_interval}s, recovery={self.RECOVERY_CHECK_INTERVAL}s"
        )

    def start(self):
        """Запуск основного цикла."""
        logger.info(f"🚀 Запуск FileMonitor с immediate-recovery")
        if not self._check_permissions():
            logger.error("❌ Недостаточно прав — остановка")
            return
        safe_mkdir(self.external_path, mode=0o755)
        safe_mkdir(self.shared_path, mode=0o755)
        # 🔹 МГНОВЕННОЕ ВОССТАНОВЛЕНИЕ ПРИ СТАРТЕ
        self._recover_stuck_jobs()
        # 🔹 Основной цикл
        iteration = 0
        while True:
            iteration += 1
            current_time = time.time()
            try:
                if current_time - self._last_incoming_check >= self.incoming_interval:
                    self._check_incoming_files()
                    self._last_incoming_check = current_time
                if current_time - self._last_recovery_check >= self.RECOVERY_CHECK_INTERVAL:
                    self._recover_stuck_jobs()
                    self._last_recovery_check = current_time
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("🛑 Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле: {e}", exc_info=True)
                time.sleep(5)

    def _check_permissions(self) -> bool:
        """Проверка прав доступа к мониторинговым папкам."""
        errors = []
        if not os.access(self.external_path, os.R_OK | os.X_OK):
            errors.append(f"Нет прав на чтение/вход в {self.external_path}")
        if not os.access(self.shared_path, os.W_OK | os.X_OK):
            errors.append(f"Нет прав на запись/вход в {self.shared_path}")
        if errors:
            for err in errors:
                logger.error(f"❌ {err}")
            return False
        return True

    def _check_incoming_files(self):
        """Проверка новых файлов во внешней папке."""
        if not self.external_path.exists():
            return
        if len(self._file_cache) > 500:
            self._file_cache = dict(list(self._file_cache.items())[-500:])
        for item in self.external_path.iterdir():
            if not item.is_file() or item.name.startswith('.'):
                continue
            if not self._is_file_ready(item):
                continue
            source_fp = get_file_fingerprint(item, use_content=True)
            if source_fp and is_file_already_processed_by_fingerprint(source_fp, self.redis):
                logger.info(f"✅ Дубликат обнаружен (fp: {source_fp}), пропускаем: {item.name}")
                self.redis.publish_event("files:events", {
                    "type": "log_only", "log_level": "WARNING",
                    "log_msg": f"🗑️ Дубликат удалён: {item.name}",
                    "filename": item.name, "fingerprint": source_fp,
                    "timestamp": datetime.now(timezone.utc).isoformat(), "ui_action": "none"
                })
                try:
                    item.unlink()
                    logger.info(f"🗑️ Дубликат удалён: {item.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить дубликат {item.name}: {e}")
                continue
            file_id = str(uuid.uuid4())[:8]
            if not self._process_new_file(item, file_id, source_fp):
                logger.warning(f"⏸️ Файл {item.name} не обработан")

    def _is_file_ready(self, file_path: Path) -> bool:
        """Проверка что файл готов к обработке."""
        try:
            stat = file_path.stat()
            if stat.st_size < self.MIN_FILE_SIZE:
                return False
            current_time = time.time()
            cache_key = str(file_path)
            if cache_key in self._file_cache:
                first_seen, cached_mtime, cached_size = self._file_cache[cache_key]
                if stat.st_mtime != cached_mtime or stat.st_size != cached_size:
                    self._file_cache[cache_key] = (current_time, stat.st_mtime, stat.st_size)
                    return False
                if current_time - first_seen >= self.FILE_STABLE_TIME:
                    del self._file_cache[cache_key]
                    return True
                return False
            self._file_cache[cache_key] = (current_time, stat.st_mtime, stat.st_size)
            return False
        except Exception:
            return False

    def _process_new_file(self, source_path: Path, file_id: str, precomputed_fingerprint: Optional[str] = None) -> bool:
        """Обработка нового файла."""
        try:
            base_dir = self.shared_path / file_id
            original_dir = base_dir / "original"
            dest_path = original_dir / source_path.name

            if base_dir.exists():
                if dest_path.exists() and source_path.exists():
                    source_path.unlink()
                return False

            safe_mkdir(original_dir, mode=0o755)
            shutil.copy2(source_path, dest_path)

            if not dest_path.exists():
                raise RuntimeError("Копия не создана")

            # 🔹 ВАЖНО: получаем размер файла ДО удаления источника!
            file_size = source_path.stat().st_size
            if dest_path.stat().st_size != file_size:
                raise RuntimeError("Несоответствие размеров копии")

            # 🔹 Теперь можно безопасно удалить исходный файл
            source_path.unlink()
            logger.info(f"✅ Исходный файл потреблён и удалён: {source_path.name}")

            fingerprint = precomputed_fingerprint or get_file_fingerprint(dest_path, use_content=True)

            ext = source_path.suffix.lower()  # suffix работает, т.к. Path-объект ещё хранит имя
            type_map = {
                ".pdf": FileType.PDF, ".doc": FileType.DOCUMENT, ".docx": FileType.DOCUMENT,
                ".png": FileType.IMAGE, ".jpg": FileType.IMAGE, ".jpeg": FileType.IMAGE,
                ".txt": FileType.TEXT, ".csv": FileType.TEXT, ".json": FileType.TEXT
            }
            file_type = type_map.get(ext, FileType.UNKNOWN)

            job = FileJob(
                file_id=file_id,
                original_filename=source_path.name,
                file_type=file_type,
                file_size=file_size,  # 🔹 Используем сохранённое значение, а не stat()
                status=FileStatus.UPLOADED,
                current_module="preprocess",
                export_to_1c=True,
                metadata={
                    "file_fingerprint": fingerprint,
                    "source_consumed_at": datetime.now(timezone.utc).isoformat()
                } if fingerprint else {},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            self.redis.set_file_status(file_id, job.to_dict())
            if fingerprint:
                update_fingerprint_index(self.redis, file_id, fingerprint)
            self.redis.push_to_queue("files:preprocess", job.to_payload(), priority=job.priority)

            self.redis.publish_event("files:events", {
                "type": "file_uploaded",
                "file_id": file_id,
                "filename": source_path.name,
                "status": FileStatus.UPLOADED.value,
                "file_type": file_type.value,
                "file_size": file_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка обработки {source_path.name}: {e}", exc_info=True)
            return False

    def _recover_stuck_jobs(self) -> Dict[str, int]:
        """Восстановление зависших джобов."""
        stats = {"recovered": 0, "failed": 0, "skipped": 0, "errors": 0}
        try:
            all_jobs = self.redis.get_all_files() or []
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.RECOVERY_GRACE_PERIOD_MINUTES)
            logger.debug(f"🔍 Recovery: проверяю {len(all_jobs)} записей в Redis")
            for job_data in all_jobs:
                if job_data.get("status") != "processing":
                    stats["skipped"] += 1
                    continue
                updated_str = job_data.get("updated_at")
                if updated_str:
                    try:
                        updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                        if updated_dt > cutoff:
                            stats["skipped"] += 1
                            continue
                    except:
                        pass
                file_id = job_data.get("file_id")
                current_module = job_data.get("current_module")
                filename = job_data.get("original_filename", "")
                if not validate_file_exists(file_id, filename, self.shared_path):
                    logger.warning(f"🗑️ Файл {file_id} ({filename}) утерян. Помечаю как failed.")
                    self._mark_job_failed(file_id, job_data, "Original file missing from disk")
                    stats["failed"] += 1
                    continue
                queue_name = self.module_queues.get(current_module)
                if not queue_name:
                    stats["skipped"] += 1
                    continue
                try:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    job_data["updated_at"] = now_iso
                    job_data["recovered_at"] = now_iso
                    job_data["recovery_count"] = job_data.get("recovery_count", 0) + 1
                    self.redis.set_file_status(file_id, job_data)
                    self.redis.push_to_queue(queue_name, json.dumps(job_data, ensure_ascii=False))
                    self.redis.publish_event("files:events", {
                        "type": "log_only", "log_level": "INFO",
                        "log_msg": f"🔄 Обработка возобновлена: {filename} (этап: {current_module})",
                        "timestamp": now_iso, "ui_action": "none"
                    })
                    stats["recovered"] += 1
                    logger.info(f"🔄 Восстановлен: {file_id} → {queue_name} (попытка #{job_data['recovery_count']})")
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"❌ Ошибка восстановления {file_id}: {e}")
            if stats["recovered"] > 0 or stats["failed"] > 0:
                logger.info(f"✅ Recovery итог: +{stats['recovered']} в очередь, {stats['failed']} в failed")
            return stats
        except Exception as e:
            logger.error(f"❌ Сбой recovery: {e}", exc_info=True)
            return stats

    def _mark_job_failed(self, file_id: str, job_data: Dict[str, Any], reason: str) -> bool:
        """Помечает джоб как failed."""
        try:
            job_data["status"] = "failed"
            job_data["errors"] = job_data.get("errors", []) + [reason]
            job_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self.redis.set_file_status(file_id, job_data)
        except Exception as e:
            logger.error(f"❌ Не удалось пометить {file_id} как failed: {e}")
            return False


def main():
    logger.info("🚀 Запуск FileMonitor...")
    try:
        FileMonitor().start()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()