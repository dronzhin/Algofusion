# monitor/file_monitor.py
"""
Мониторинг внешней папки для новых файлов.
🔹 Паттерн Consume-on-Read + Content-Based Fingerprint
🔹 Дубликаты: только лог в UI, никаких других эффектов.
"""

import time
import shutil
import uuid
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from shared.models.file import FileJob, FileStatus
from shared.models.file.enums import FileType
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import (
    safe_mkdir,
    get_file_fingerprint,
    is_file_already_processed_by_fingerprint,
    update_fingerprint_index,
    FILE_FINGERPRINT_INDEX
)
from core.services.redis_client import get_redis_client

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """Мониторит внешнюю папку и создаёт задания для новых файлов."""

    MIN_FILE_SIZE = 1024  # 1 KB
    FILE_STABLE_TIME = 2  # секунды стабильности файла

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
        self.redis = get_redis_client()

        self._file_cache: dict[str, tuple[float, float, int]] = {}

        logger.info(
            f"FileMonitor инициализирован: "
            f"external={self.external_path}, "
            f"shared={self.shared_path}, "
            f"interval={self.check_interval}s"
        )

    def start(self):
        """Запуск цикла мониторинга."""
        logger.info(f"Запуск мониторинга папки {self.external_path}")

        if not self._check_permissions():
            logger.error("❌ Недостаточно прав для работы монитора — остановка")
            return

        safe_mkdir(self.external_path, mode=0o755)
        safe_mkdir(self.shared_path, mode=0o755)

        self._rebuild_fingerprint_index()

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"🔄 Цикл мониторинга #{iteration}")

            try:
                self.check_for_new_files()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}", exc_info=True)
                time.sleep(self.check_interval)

    def _check_permissions(self) -> bool:
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

    def _is_file_ready(self, file_path: Path) -> bool:
        try:
            stat = file_path.stat()
            if stat.st_size < self.MIN_FILE_SIZE:
                return False

            current_time = time.time()
            file_mtime = stat.st_mtime
            file_size = stat.st_size
            cache_key = str(file_path)

            if cache_key in self._file_cache:
                first_seen_time, cached_mtime, cached_size = self._file_cache[cache_key]
                if file_mtime != cached_mtime or file_size != cached_size:
                    self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                    return False

                if current_time - first_seen_time >= self.FILE_STABLE_TIME:
                    del self._file_cache[cache_key]
                    return True
                return False
            else:
                self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                return False
        except Exception as e:
            logger.debug(f"Ошибка проверки готовности {file_path.name}: {e}")
            return False

    def check_for_new_files(self):
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

            # 🔹 1. Вычисляем fingerprint ДО любых действий
            source_fp = get_file_fingerprint(item, use_content=True)

            # 🔹 2. Проверяем Redis на наличие такого же файла
            if source_fp and is_file_already_processed_by_fingerprint(source_fp, self.redis):
                logger.info(f"✅ Дубликат обнаружен (fp: {source_fp}), пропускаем: {item.name}")

                # 🔹 ПУБЛИКУЕМ СОБЫТИЕ ТОЛЬКО ДЛЯ ЛОГОВ
                # Этот тип события UI обработает как "только в журнал, никаких других действий"
                self.redis.publish_event("files:events", {
                    "type": "log_only",
                    "log_level": "WARNING",
                    "log_msg": f"🗑️ Дубликат удалён: {item.name}",
                    "filename": item.name,
                    "fingerprint": source_fp,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ui_action": "none"
                })

                # Физическое удаление файла
                try:
                    item.unlink()
                    logger.info(f"🗑️ Исходный файл-дубликат удалён: {item.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить дубликат {item.name}: {e}")
                continue

            # 🔹 3. Файл новый → обрабатываем
            file_id = str(uuid.uuid4())[:8]
            success = self.process_new_file(item, file_id, source_fp)

            if not success:
                logger.warning(f"⏸️ Файл {item.name} не обработан, останется во входящей папке")

    def process_new_file(self, source_path: Path, file_id: str, precomputed_fingerprint: Optional[str] = None) -> bool:
        try:
            base_dir = self.shared_path / file_id
            original_dir = base_dir / "original"
            dest_path = original_dir / source_path.name

            if base_dir.exists():
                logger.warning(f"⚠️ Директория {file_id} уже существует. Пропускаем.")
                if dest_path.exists() and source_path.exists():
                    source_path.unlink()
                return False

            safe_mkdir(original_dir, mode=0o755)
            shutil.copy2(source_path, dest_path)

            if not dest_path.exists():
                raise RuntimeError("Копия не создана")

            src_stat = source_path.stat()
            dst_stat = dest_path.stat()
            if dst_stat.st_size != src_stat.st_size:
                raise RuntimeError(f"Несоответствие размеров: исходный {src_stat.st_size} != копия {dst_stat.st_size}")

            source_path.unlink()
            logger.info(f"✅ Исходный файл потреблён и удалён: {source_path.name}")

            fingerprint = precomputed_fingerprint or get_file_fingerprint(dest_path, use_content=True)

            ext = source_path.suffix.lower()
            type_map = {
                ".pdf": FileType.PDF,
                ".doc": FileType.DOCUMENT, ".docx": FileType.DOCUMENT,
                ".png": FileType.IMAGE, ".jpg": FileType.IMAGE, ".jpeg": FileType.IMAGE,
                ".txt": FileType.TEXT, ".csv": FileType.TEXT, ".json": FileType.TEXT
            }
            file_type = type_map.get(ext, FileType.UNKNOWN)

            job = FileJob(
                file_id=file_id,
                original_filename=source_path.name,
                file_type=file_type,
                file_size=src_stat.st_size,
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
                "file_size": src_stat.st_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"✅ Файл {file_id} успешно добавлен в пайплайн (fp: {fingerprint})")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка обработки {source_path.name}: {e}", exc_info=True)
            self._publish_error_event(source_path.name, str(e))
            return False

    def _publish_error_event(self, filename: str, error: str):
        try:
            self.redis.publish_event("files:events", {
                "type": "file_error", "filename": filename, "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Не удалось опубликовать событие: {e}")

    def _rebuild_fingerprint_index(self):
        logger.info("🔍 Восстановление индексов fingerprint...")
        try:
            all_files = self.redis.get_all_files()
            rebuilt = 0
            for file_data in all_files:
                fp = file_data.get("metadata", {}).get("file_fingerprint")
                fid = file_data.get("file_id")
                if fp and fid:
                    existing = self.redis.get(FILE_FINGERPRINT_INDEX.format(fingerprint=fp))
                    if not existing or existing != fid:
                        update_fingerprint_index(self.redis, fid, fp)
                        rebuilt += 1
            if rebuilt:
                logger.info(f"✅ Восстановлено {rebuilt} индексов fingerprint")
            else:
                logger.debug("✅ Все индексы в порядке")
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления индексов: {e}")


def main():
    logger.info("Запуск FileMonitor...")
    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()