# monitor/file_monitor.py
"""
РњРѕРЅРёС‚РѕСЂРёРЅРі РІРЅРµС€РЅРµР№ РїР°РїРєРё РґР»СЏ РЅРѕРІС‹С… С„Р°Р№Р»РѕРІ.
Р—Р°РїСѓСЃРєР°РµС‚СЃСЏ РєР°Рє РѕС‚РґРµР»СЊРЅС‹Р№ РєРѕРЅС‚РµР№РЅРµСЂ.
"""

import time
import shutil
import uuid
import os
from pathlib import Path
from typing import Set, Optional
from datetime import datetime, timezone  # в†ђ FIX: Р”РѕР±Р°РІРёР»Рё timezone

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir
from core.services.redis_client import get_redis_client

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """РњРѕРЅРёС‚РѕСЂРёС‚ РІРЅРµС€РЅСЋСЋ РїР°РїРєСѓ Рё СЃРѕР·РґР°С‘С‚ Р·Р°РґР°РЅРёСЏ РґР»СЏ РЅРѕРІС‹С… С„Р°Р№Р»РѕРІ."""

    # РњРёРЅРёРјР°Р»СЊРЅС‹Р№ СЂР°Р·РјРµСЂ С„Р°Р№Р»Р°, С‡С‚РѕР±С‹ СЃС‡РёС‚Р°С‚СЊ РµРіРѕ "РіРѕС‚РѕРІС‹Рј" (Р·Р°С‰РёС‚Р° РѕС‚ РєРѕРїРёСЂРѕРІР°РЅРёСЏ)
    MIN_FILE_SIZE = 1024  # 1 KB
    # Р’СЂРµРјСЏ СЃС‚Р°Р±РёР»СЊРЅРѕСЃС‚Рё С„Р°Р№Р»Р° (СЃРµРє) вЂ” С„Р°Р№Р» РЅРµ РјРµРЅСЏР»СЃСЏ, Р·РЅР°С‡РёС‚ РіРѕС‚РѕРІ Рє РѕР±СЂР°Р±РѕС‚РєРµ
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
            f"FileMonitor РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ: "
            f"external={self.external_path}, "
            f"shared={self.shared_path}, "
            f"interval={self.check_interval}s"
        )

    def start(self):
        """Р—Р°РїСѓСЃРє С†РёРєР»Р° РјРѕРЅРёС‚РѕСЂРёРЅРіР°."""
        logger.info(f"Р—Р°РїСѓСЃРє РјРѕРЅРёС‚РѕСЂРёРЅРіР° РїР°РїРєРё {self.external_path}")

        if not self._check_permissions():
            logger.error("вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ РґР»СЏ СЂР°Р±РѕС‚С‹ РјРѕРЅРёС‚РѕСЂР° вЂ” РѕСЃС‚Р°РЅРѕРІРєР°")
            return

        safe_mkdir(self.external_path, mode=0o755)
        safe_mkdir(self.shared_path, mode=0o755)

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"рџ”„ Р¦РёРєР» РјРѕРЅРёС‚РѕСЂРёРЅРіР° #{iteration}")

            try:
                self.check_for_new_files()
                logger.debug(f"рџ’¤ РЎРїР»СЋ {self.check_interval}СЃРµРє...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("РњРѕРЅРёС‚РѕСЂРёРЅРі РѕСЃС‚Р°РЅРѕРІР»РµРЅ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј")
                break
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РІ С†РёРєР»Рµ: {e}", exc_info=True)
                time.sleep(self.check_interval)
    def _check_permissions(self) -> bool:
        """Check access by performing real directory and file operations."""
        try:
            safe_mkdir(self.external_path, mode=0o755)
            safe_mkdir(self.shared_path, mode=0o755)

            probe_dir = self.shared_path / ".monitor_probe"
            safe_mkdir(probe_dir, mode=0o755)
            probe_file = probe_dir / ".write_test"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)

            logger.debug("Permission check passed")
            return True
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        РџСЂРѕРІРµСЂРєР° С‡С‚Рѕ С„Р°Р№Р» "РіРѕС‚РѕРІ" Рє РѕР±СЂР°Р±РѕС‚РєРµ:
        - Р Р°Р·РјРµСЂ > РјРёРЅРёРјР°Р»СЊРЅРѕРіРѕ
        - РќРµ РјРµРЅСЏР»СЃСЏ РїРѕСЃР»РµРґРЅРёРµ FILE_STABLE_TIME СЃРµРєСѓРЅРґ
        - РќРµ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ РґСЂСѓРіРёРј РїСЂРѕС†РµСЃСЃРѕРј
        """
        try:
            stat = file_path.stat()

            # РџСЂРѕРІРµСЂРєР° РјРёРЅРёРјР°Р»СЊРЅРѕРіРѕ СЂР°Р·РјРµСЂР°
            if stat.st_size < self.MIN_FILE_SIZE:
                logger.debug(f"  вќЊ {file_path.name}: СЂР°Р·РјРµСЂ {stat.st_size} < {self.MIN_FILE_SIZE}")
                return False

            current_time = time.time()
            file_mtime = stat.st_mtime  # в†ђ Р’СЂРµРјСЏ РјРѕРґРёС„РёРєР°С†РёРё С„Р°Р№Р»Р°
            file_size = stat.st_size

            # в†ђ FIX: РСЃРїРѕР»СЊР·СѓРµРј СЃС‚СЂРѕРєРѕРІС‹Р№ РїСѓС‚СЊ РґР»СЏ РЅР°РґС‘Р¶РЅРѕСЃС‚Рё
            cache_key = str(file_path)

            if cache_key in self._file_cache:
                first_seen_time, cached_mtime, cached_size = self._file_cache[cache_key]

                # Р•СЃР»Рё СЂР°Р·РјРµСЂ РёР»Рё mtime С„Р°Р№Р»Р° РёР·РјРµРЅРёР»РёСЃСЊ вЂ” С„Р°Р№Р» РµС‰С‘ РїРёС€РµС‚СЃСЏ
                if file_mtime != cached_mtime or file_size != cached_size:
                    logger.debug(f"  рџ”„ {file_path.name}: С„Р°Р№Р» РёР·РјРµРЅРёР»СЃСЏ, СЃР±СЂРѕСЃ РєСЌС€Р°")
                    # в†ђ FIX: РћР±РЅРѕРІР»СЏРµРј РІСЂРµРјСЏ РїРµСЂРІРѕРіРѕ РЅР°Р±Р»СЋРґРµРЅРёСЏ
                    self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                    return False

                # в†ђ FIX: РЎСЂР°РІРЅРёРІР°РµРј СЃ Р’Р Р•РњР•РќР•Рњ РџР•Р Р’РћР“Рћ РќРђР‘Р›Р®Р”Р•РќРРЇ, Р° РЅРµ mtime С„Р°Р№Р»Р°!
                time_since_first_seen = current_time - first_seen_time

                logger.debug(
                    f"  вЏ± {file_path.name}: РЅР°Р±Р»СЋРґР°РµС‚СЃСЏ {time_since_first_seen:.1f}СЃРµРє (РЅСѓР¶РЅРѕ {self.FILE_STABLE_TIME}СЃРµРє)")

                if time_since_first_seen >= self.FILE_STABLE_TIME:
                    logger.debug(f"  вњ… {file_path.name}: Р“РћРўРћР’ Рє РѕР±СЂР°Р±РѕС‚РєРµ!")
                    del self._file_cache[cache_key]
                    return True
                else:
                    return False
            else:
                # в†ђ FIX: РЎРѕС…СЂР°РЅСЏРµРј (РІСЂРµРјСЏ_РЅР°Р±Р»СЋРґРµРЅРёСЏ, mtime_С„Р°Р№Р»Р°, СЂР°Р·РјРµСЂ_С„Р°Р№Р»Р°)
                logger.debug(f"  рџ“ќ {file_path.name}: РїРµСЂРІРѕРµ РЅР°Р±Р»СЋРґРµРЅРёРµ, РґРѕР±Р°РІР»СЏРµРј РІ РєСЌС€")
                self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                return False

        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"  вљ  {file_path.name}: РЅРµРґРѕСЃС‚СѓРїРµРЅ ({e})")
            return False
        except Exception as e:
            logger.warning(f"РћС€РёР±РєР° РїСЂРѕРІРµСЂРєРё РіРѕС‚РѕРІРЅРѕСЃС‚Рё С„Р°Р№Р»Р° {file_path}: {e}")
            return False

    def check_for_new_files(self):
        """РџСЂРѕРІРµСЂРєР° РЅРѕРІС‹С… С„Р°Р№Р»РѕРІ РІРѕ РІРЅРµС€РЅРµР№ РїР°РїРєРµ."""
        logger.debug("рџ”Ќ check_for_new_files: РќРђР§РђР›Рћ")

        if not self.external_path.exists():
            logger.warning(f"Р’РЅРµС€РЅСЏСЏ РїР°РїРєР° РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚: {self.external_path}")
            return

        logger.debug(f"рџ“‚ РЎРєР°РЅРёСЂСѓРµРј: {self.external_path}")

        files_count = 0
        for item in self.external_path.iterdir():
            files_count += 1
            logger.debug(f"  [{files_count}] {item.name} (file={item.is_file()})")

            if item.is_file() and not item.name.startswith('.'):
                logger.debug(f"    в†’ РџСЂРѕРІРµСЂСЏРµРј РіРѕС‚РѕРІРЅРѕСЃС‚СЊ: {item.name}")

                if not self._is_file_ready(item):
                    logger.debug(f"    в†’ Р¤Р°Р№Р» РЅРµ РіРѕС‚РѕРІ, РїСЂРѕРїСѓСЃРєР°РµРј")
                    continue

                logger.debug(f"    в†’ Р¤Р°Р№Р» РіРѕС‚РѕРІ! РћР±СЂР°Р±Р°С‚С‹РІР°РµРј...")

                file_stat = item.stat()
                cache_key = f"{item.name}:{file_stat.st_mtime}:{file_stat.st_size}"

                if cache_key not in self.processed_files:
                    logger.info(f"РћР±РЅР°СЂСѓР¶РµРЅ РЅРѕРІС‹Р№ С„Р°Р№Р»: {item.name} ({file_stat.st_size} Р±Р°Р№С‚)")
                    file_id = str(uuid.uuid4())[:8]
                    success = self.process_new_file(item, file_id)

                    if success:
                        self.processed_files.add(cache_key)
                        if len(self.processed_files) > 1000:
                            self.processed_files = set(list(self.processed_files)[-1000:])
                    else:
                        logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ С„Р°Р№Р» {item.name}")
                else:
                    logger.debug(f"    в†’ Р¤Р°Р№Р» СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅ (РІ РєСЌС€Рµ)")

        logger.debug(f"вњ… check_for_new_files: Р—РђР’Р•Р РЁР•РќРћ (С„Р°Р№Р»РѕРІ: {files_count})")

    def process_new_file(self, file_path: Path, file_id: str) -> bool:
        """
        РћР±СЂР°Р±РѕС‚РєР° РЅРѕРІРѕРіРѕ С„Р°Р№Р»Р°: СЃРѕР·РґР°РЅРёРµ СЃС‚СЂСѓРєС‚СѓСЂС‹ Рё РѕС‚РїСЂР°РІРєР° РІ РѕС‡РµСЂРµРґСЊ.

        Returns:
            True РµСЃР»Рё РѕР±СЂР°Р±РѕС‚РєР° СѓСЃРїРµС€РЅР°, False РµСЃР»Рё РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР°
        """
        try:
            # в†ђ FIX: РЎРѕР·РґР°С‘Рј СЃС‚СЂСѓРєС‚СѓСЂСѓ СЃ СЏРІРЅС‹РјРё РїСЂР°РІР°РјРё
            base_dir = self.shared_path / file_id
            original_dir = base_dir / "original"
            safe_mkdir(original_dir, mode=0o755)

            # РљРѕРїРёСЂСѓРµРј С„Р°Р№Р» СЃ СЃРѕС…СЂР°РЅРµРЅРёРµРј РјРµС‚Р°РґР°РЅРЅС‹С…
            dest_path = original_dir / file_path.name

            # в†ђ FIX: РџСЂРѕРІРµСЂРєР° С‡С‚Рѕ С„Р°Р№Р» РµС‰С‘ РґРѕСЃС‚СѓРїРµРЅ РїРµСЂРµРґ РєРѕРїРёСЂРѕРІР°РЅРёРµРј
            if not file_path.exists():
                logger.warning(f"Р¤Р°Р№Р» РёСЃС‡РµР· РїРµСЂРµРґ РєРѕРїРёСЂРѕРІР°РЅРёРµРј: {file_path}")
                return False

            shutil.copy2(file_path, dest_path)

            # в†ђ FIX: РЇРІРЅРѕ СѓСЃС‚Р°РЅР°РІР»РёРІР°РµРј РїСЂР°РІР° РЅР° СЃРєРѕРїРёСЂРѕРІР°РЅРЅС‹Р№ С„Р°Р№Р»
            try:
                os.chmod(dest_path, 0o644)  # Р§С‚РµРЅРёРµ РґР»СЏ РІСЃРµС…, Р·Р°РїРёСЃСЊ РґР»СЏ РІР»Р°РґРµР»СЊС†Р°
            except PermissionError:
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓСЃС‚Р°РЅРѕРІРёС‚СЊ РїСЂР°РІР° РЅР° {dest_path}")

            logger.info(f"Р¤Р°Р№Р» СЃРєРѕРїРёСЂРѕРІР°РЅ: {file_path} в†’ {dest_path}")

            # РЎРѕР·РґР°С‘Рј FileJob
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

            # РЎРѕС…СЂР°РЅСЏРµРј СЃС‚Р°С‚СѓСЃ РІ Redis
            self.redis.set_file_status(file_id, job.to_dict())

            # РћС‚РїСЂР°РІР»СЏРµРј РІ РѕС‡РµСЂРµРґСЊ preprocess
            self.redis.push_to_queue("files:cleaner", job.to_payload(), priority=job.priority)

            # РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ РґР»СЏ UI
            self.redis.publish_event("files:events", {
                "type": "file_uploaded",
                "file_id": file_id,
                "filename": file_path.name,
                "status": job.status.value,
                "file_type": file_type.value,
                "file_size": file_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"Р¤Р°Р№Р» {file_id} РґРѕР±Р°РІР»РµРЅ РІ РѕС‡РµСЂРµРґСЊ РѕР±СЂР°Р±РѕС‚РєРё")
            return True

        except PermissionError as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ {file_path}: {e}")
            logger.error(f"рџ’Ў РџСЂРѕРІРµСЂСЊС‚Рµ РїСЂР°РІР°: ls -la {file_path.parent}")
            self._publish_error_event(file_path.name, f"PermissionError: {e}")
            return False

        except shutil.Error as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РєРѕРїРёСЂРѕРІР°РЅРёСЏ {file_path}: {e}")
            self._publish_error_event(file_path.name, f"CopyError: {e}")
            return False

        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё С„Р°Р№Р»Р° {file_path}: {e}", exc_info=True)
            self._publish_error_event(file_path.name, str(e))
            return False

    def _publish_error_event(self, filename: str, error: str):
        """РџСѓР±Р»РёРєР°С†РёСЏ СЃРѕР±С‹С‚РёСЏ РѕР± РѕС€РёР±РєРµ РґР»СЏ UI."""
        try:
            self.redis.publish_event("files:events", {
                "type": "file_error",
                "filename": filename,
                "error": error,
                # в†ђ FIX: timezone-aware timestamp
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСѓР±Р»РёРєРѕРІР°С‚СЊ СЃРѕР±С‹С‚РёРµ РѕР± РѕС€РёР±РєРµ: {e}")

    def cleanup_cache(self):
        """РћС‡РёСЃС‚РєР° РєСЌС€Р° РѕР±СЂР°Р±РѕС‚Р°РЅРЅС‹С… С„Р°Р№Р»РѕРІ (РґР»СЏ РїСЂРµРґРѕС‚РІСЂР°С‰РµРЅРёСЏ СѓС‚РµС‡РµРє РїР°РјСЏС‚Рё)."""
        # РћСЃС‚Р°РІР»СЏРµРј С‚РѕР»СЊРєРѕ РїРѕСЃР»РµРґРЅРёРµ 500 Р·Р°РїРёСЃРµР№
        if len(self.processed_files) > 500:
            old_count = len(self.processed_files)
            self.processed_files = set(list(self.processed_files)[-500:])
            logger.debug(f"РљСЌС€ РѕР±СЂР°Р±РѕС‚Р°РЅРЅС‹С… С„Р°Р№Р»РѕРІ РѕС‡РёС‰РµРЅ: {old_count} в†’ {len(self.processed_files)}")


def main():
    """РўРѕС‡РєР° РІС…РѕРґР° РґР»СЏ РєРѕРЅС‚РµР№РЅРµСЂР° monitor."""
    logger.info("Р—Р°РїСѓСЃРє FileMonitor...")

    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР°: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
