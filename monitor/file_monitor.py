# monitor/file_monitor.py
"""
Мониторинг внешней папки для новых файлов.
Запускается как отдельный контейнер.
"""

import time
import shutil
import uuid
import os
from pathlib import Path
from typing import Set, Optional
from datetime import datetime, timezone  # ← FIX: Добавили timezone

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir
from core.services.redis_client import get_redis_client

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """Мониторит внешнюю папку и создаёт задания для новых файлов."""

    # Минимальный размер файла, чтобы считать его "готовым" (защита от копирования)
    MIN_FILE_SIZE = 1024  # 1 KB
    # Время стабильности файла (сек) — файл не менялся, значит готов к обработке
    FILE_STABLE_TIME = 2

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
        self.processed_files: Set[str] = set()
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

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"🔄 Цикл мониторинга #{iteration}")

            try:
                self.check_for_new_files()
                logger.debug(f"💤 Сплю {self.check_interval}сек...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}", exc_info=True)
                time.sleep(self.check_interval)
    def _check_permissions(self) -> bool:
        """
        Проверка прав доступа к мониторинговым папкам.
        Возвращает True если все права в порядке.
        """
        errors = []

        # Проверка внешней папки (чтение + выполнение для входа)
        if not os.access(self.external_path, os.R_OK | os.X_OK):
            errors.append(f"Нет прав на чтение/вход в {self.external_path}")

        # Проверка shared-папки (запись + выполнение)
        if not os.access(self.shared_path, os.W_OK | os.X_OK):
            errors.append(f"Нет прав на запись/вход в {self.shared_path}")

        if errors:
            for err in errors:
                logger.error(f"❌ {err}")
            logger.error(
                f"💡 Исправление: "
                f"sudo chown -R $USER:$USER {self.external_path} {self.shared_path} && "
                f"sudo chmod -R 755 {self.external_path} {self.shared_path}"
            )
            return False

        logger.debug("✓ Права доступа проверены")
        return True

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Проверка что файл "готов" к обработке:
        - Размер > минимального
        - Не менялся последние FILE_STABLE_TIME секунд
        - Не заблокирован другим процессом
        """
        try:
            stat = file_path.stat()

            # Проверка минимального размера
            if stat.st_size < self.MIN_FILE_SIZE:
                logger.debug(f"  ❌ {file_path.name}: размер {stat.st_size} < {self.MIN_FILE_SIZE}")
                return False

            current_time = time.time()
            file_mtime = stat.st_mtime  # ← Время модификации файла
            file_size = stat.st_size

            # ← FIX: Используем строковый путь для надёжности
            cache_key = str(file_path)

            if cache_key in self._file_cache:
                first_seen_time, cached_mtime, cached_size = self._file_cache[cache_key]

                # Если размер или mtime файла изменились — файл ещё пишется
                if file_mtime != cached_mtime or file_size != cached_size:
                    logger.debug(f"  🔄 {file_path.name}: файл изменился, сброс кэша")
                    # ← FIX: Обновляем время первого наблюдения
                    self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                    return False

                # ← FIX: Сравниваем с ВРЕМЕНЕМ ПЕРВОГО НАБЛЮДЕНИЯ, а не mtime файла!
                time_since_first_seen = current_time - first_seen_time

                logger.debug(
                    f"  ⏱ {file_path.name}: наблюдается {time_since_first_seen:.1f}сек (нужно {self.FILE_STABLE_TIME}сек)")

                if time_since_first_seen >= self.FILE_STABLE_TIME:
                    logger.debug(f"  ✅ {file_path.name}: ГОТОВ к обработке!")
                    del self._file_cache[cache_key]
                    return True
                else:
                    return False
            else:
                # ← FIX: Сохраняем (время_наблюдения, mtime_файла, размер_файла)
                logger.debug(f"  📝 {file_path.name}: первое наблюдение, добавляем в кэш")
                self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                return False

        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"  ⚠ {file_path.name}: недоступен ({e})")
            return False
        except Exception as e:
            logger.warning(f"Ошибка проверки готовности файла {file_path}: {e}")
            return False

    def check_for_new_files(self):
        """Проверка новых файлов во внешней папке."""
        logger.debug("🔍 check_for_new_files: НАЧАЛО")

        if not self.external_path.exists():
            logger.warning(f"Внешняя папка не существует: {self.external_path}")
            return

        logger.debug(f"📂 Сканируем: {self.external_path}")

        files_count = 0
        for item in self.external_path.iterdir():
            files_count += 1
            logger.debug(f"  [{files_count}] {item.name} (file={item.is_file()})")

            if item.is_file() and not item.name.startswith('.'):
                logger.debug(f"    → Проверяем готовность: {item.name}")

                if not self._is_file_ready(item):
                    logger.debug(f"    → Файл не готов, пропускаем")
                    continue

                logger.debug(f"    → Файл готов! Обрабатываем...")

                file_stat = item.stat()
                cache_key = f"{item.name}:{file_stat.st_mtime}:{file_stat.st_size}"

                if cache_key not in self.processed_files:
                    logger.info(f"Обнаружен новый файл: {item.name} ({file_stat.st_size} байт)")
                    file_id = str(uuid.uuid4())[:8]
                    success = self.process_new_file(item, file_id)

                    if success:
                        self.processed_files.add(cache_key)
                        if len(self.processed_files) > 1000:
                            self.processed_files = set(list(self.processed_files)[-1000:])
                    else:
                        logger.warning(f"Не удалось обработать файл {item.name}")
                else:
                    logger.debug(f"    → Файл уже обработан (в кэше)")

        logger.debug(f"✅ check_for_new_files: ЗАВЕРШЕНО (файлов: {files_count})")

    def process_new_file(self, file_path: Path, file_id: str) -> bool:
        """
        Обработка нового файла: создание структуры и отправка в очередь.

        Returns:
            True если обработка успешна, False если произошла ошибка
        """
        try:
            # ← FIX: Создаём структуру с явными правами
            base_dir = self.shared_path / file_id
            original_dir = base_dir / "original"
            safe_mkdir(original_dir, mode=0o755)

            # Копируем файл с сохранением метаданных
            dest_path = original_dir / file_path.name

            # ← FIX: Проверка что файл ещё доступен перед копированием
            if not file_path.exists():
                logger.warning(f"Файл исчез перед копированием: {file_path}")
                return False

            shutil.copy2(file_path, dest_path)

            # ← FIX: Явно устанавливаем права на скопированный файл
            try:
                os.chmod(dest_path, 0o644)  # Чтение для всех, запись для владельца
            except PermissionError:
                logger.warning(f"Не удалось установить права на {dest_path}")

            logger.info(f"Файл скопирован: {file_path} → {dest_path}")

            # Создаём FileJob
            file_type = FileJob.detect_file_type(file_path.name)
            file_size = file_path.stat().st_size

            job = FileJob(
                file_id=file_id,
                original_filename=file_path.name,
                file_type=file_type,
                file_size=file_size,
                status=FileStatus.UPLOADED,
                current_module="cleaner",
                export_to_1c=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Сохраняем статус в Redis
            self.redis.set_file_status(file_id, job.to_dict())

            # Отправляем в очередь preprocess
            self.redis.push_to_queue("files:cleaner", job.to_payload(), priority=job.priority)

            # Публикуем событие для UI
            self.redis.publish_event("files:events", {
                "type": "file_uploaded",
                "file_id": file_id,
                "filename": file_path.name,
                "status": job.status.value,
                "file_type": file_type.value,
                "file_size": file_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"Файл {file_id} добавлен в очередь обработки")
            return True

        except PermissionError as e:
            logger.error(f"❌ Ошибка прав доступа при обработке {file_path}: {e}")
            logger.error(f"💡 Проверьте права: ls -la {file_path.parent}")
            self._publish_error_event(file_path.name, f"PermissionError: {e}")
            return False

        except shutil.Error as e:
            logger.error(f"❌ Ошибка копирования {file_path}: {e}")
            self._publish_error_event(file_path.name, f"CopyError: {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка обработки файла {file_path}: {e}", exc_info=True)
            self._publish_error_event(file_path.name, str(e))
            return False

    def _publish_error_event(self, filename: str, error: str):
        """Публикация события об ошибке для UI."""
        try:
            self.redis.publish_event("files:events", {
                "type": "file_error",
                "filename": filename,
                "error": error,
                # ← FIX: timezone-aware timestamp
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Не удалось опубликовать событие об ошибке: {e}")

    def cleanup_cache(self):
        """Очистка кэша обработанных файлов (для предотвращения утечек памяти)."""
        # Оставляем только последние 500 записей
        if len(self.processed_files) > 500:
            old_count = len(self.processed_files)
            self.processed_files = set(list(self.processed_files)[-500:])
            logger.debug(f"Кэш обработанных файлов очищен: {old_count} → {len(self.processed_files)}")


def main():
    """Точка входа для контейнера monitor."""
    logger.info("Запуск FileMonitor...")

    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()