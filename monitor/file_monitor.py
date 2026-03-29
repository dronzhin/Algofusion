# monitor/file_monitor.py
"""
Р СљР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘Р Р…Р С– Р Р†Р Р…Р ВµРЎв‚¬Р Р…Р ВµР в„– Р С—Р В°Р С—Р С”Р С‘ Р Т‘Р В»РЎРЏ Р Р…Р С•Р Р†РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р†.
Р вЂ”Р В°Р С—РЎС“РЎРѓР С”Р В°Р ВµРЎвЂљРЎРѓРЎРЏ Р С”Р В°Р С” Р С•РЎвЂљР Т‘Р ВµР В»РЎРЉР Р…РЎвЂ№Р в„– Р С”Р С•Р Р…РЎвЂљР ВµР в„–Р Р…Р ВµРЎР‚.
"""

import time
import shutil
import uuid
import os
import json
from pathlib import Path
from typing import Set, Optional
from datetime import datetime, timezone  # РІвЂ С’ FIX: Р вЂќР С•Р В±Р В°Р Р†Р С‘Р В»Р С‘ timezone

from shared.models.file import FileJob, FileStatus
from shared.config.settings import get_settings
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir
from core.services.redis_client import get_redis_client

logger = setup_logger("monitor.file_monitor")


class FileMonitor:
    """Р СљР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘РЎвЂљ Р Р†Р Р…Р ВµРЎв‚¬Р Р…РЎР‹РЎР‹ Р С—Р В°Р С—Р С”РЎС“ Р С‘ РЎРѓР С•Р В·Р Т‘Р В°РЎвЂРЎвЂљ Р В·Р В°Р Т‘Р В°Р Р…Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р Р…Р С•Р Р†РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р†."""

    # Р СљР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…РЎвЂ№Р в„– РЎР‚Р В°Р В·Р СР ВµРЎР‚ РЎвЂћР В°Р в„–Р В»Р В°, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ РЎРѓРЎвЂЎР С‘РЎвЂљР В°РЎвЂљРЎРЉ Р ВµР С–Р С• "Р С–Р С•РЎвЂљР С•Р Р†РЎвЂ№Р С" (Р В·Р В°РЎвЂ°Р С‘РЎвЂљР В° Р С•РЎвЂљ Р С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ)
    MIN_FILE_SIZE = 1024  # 1 KB
    # Р вЂ™РЎР‚Р ВµР СРЎРЏ РЎРѓРЎвЂљР В°Р В±Р С‘Р В»РЎРЉР Р…Р С•РЎРѓРЎвЂљР С‘ РЎвЂћР В°Р в„–Р В»Р В° (РЎРѓР ВµР С”) РІР‚вЂќ РЎвЂћР В°Р в„–Р В» Р Р…Р Вµ Р СР ВµР Р…РЎРЏР В»РЎРѓРЎРЏ, Р В·Р Р…Р В°РЎвЂЎР С‘РЎвЂљ Р С–Р С•РЎвЂљР С•Р Р† Р С” Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р Вµ
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
        self.state_dir = self.shared_path / ".monitor_state"
        self.state_file = self.state_dir / "processed_files.json"
        self.processed_index: dict[str, dict[str, object]] = {}
        self._load_persistent_state()

        logger.info(
            f"FileMonitor Р С‘Р Р…Р С‘РЎвЂ Р С‘Р В°Р В»Р С‘Р В·Р С‘РЎР‚Р С•Р Р†Р В°Р Р…: "
            f"external={self.external_path}, "
            f"shared={self.shared_path}, "
            f"interval={self.check_interval}s"
        )

    def _load_persistent_state(self) -> None:
        try:
            safe_mkdir(self.state_dir, mode=0o755)
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.processed_index = data
            logger.info("Loaded %s persisted monitor fingerprints", len(self.processed_index))
        except Exception as e:
            logger.warning(f"Failed to load monitor state: {e}")
            self.processed_index = {}

    def _save_persistent_state(self) -> None:
        safe_mkdir(self.state_dir, mode=0o755)
        temp_path = self.state_file.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(self.processed_index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.state_file)

    def _build_persistent_fingerprint(self, file_path: Path, file_stat: os.stat_result) -> str:
        try:
            source = str(file_path.resolve())
        except Exception:
            source = str(file_path)
        return f"{source}|{int(file_stat.st_size)}|{int(file_stat.st_mtime_ns)}"

    def _remember_processed_file(
            self,
            file_path: Path,
            file_stat: os.stat_result,
            file_id: str,
            storage_dir: str
    ) -> None:
        fingerprint = self._build_persistent_fingerprint(file_path, file_stat)
        self.processed_index[fingerprint] = {
            "file_id": file_id,
            "storage_dir": storage_dir,
            "filename": file_path.name,
            "size": int(file_stat.st_size),
            "mtime_ns": int(file_stat.st_mtime_ns),
        }
        if len(self.processed_index) > 5000:
            self.processed_index = dict(list(self.processed_index.items())[-5000:])
        self._save_persistent_state()

    def _find_existing_import(self, file_path: Path, file_stat: os.stat_result) -> Optional[str]:
        for original_path in self.shared_path.glob(f"*/original/{file_path.name}"):
            try:
                original_stat = original_path.stat()
            except FileNotFoundError:
                continue

            if (
                    int(original_stat.st_size) == int(file_stat.st_size)
                    and int(original_stat.st_mtime_ns) == int(file_stat.st_mtime_ns)
            ):
                return original_path.parent.parent.name
        return None

    def start(self):
        """Р вЂ”Р В°Р С—РЎС“РЎРѓР С” РЎвЂ Р С‘Р С”Р В»Р В° Р СР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘Р Р…Р С–Р В°."""
        logger.info(f"Р вЂ”Р В°Р С—РЎС“РЎРѓР С” Р СР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘Р Р…Р С–Р В° Р С—Р В°Р С—Р С”Р С‘ {self.external_path}")

        if not self._check_permissions():
            logger.error("РІСњРЉ Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р С—РЎР‚Р В°Р Р† Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂ№ Р СР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р В° РІР‚вЂќ Р С•РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р С”Р В°")
            return

        safe_mkdir(self.external_path, mode=0o755)
        safe_mkdir(self.shared_path, mode=0o755)

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"СЂСџвЂќвЂћ Р В¦Р С‘Р С”Р В» Р СР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘Р Р…Р С–Р В° #{iteration}")

            try:
                self.check_for_new_files()
                logger.debug(f"СЂСџвЂ™В¤ Р РЋР С—Р В»РЎР‹ {self.check_interval}РЎРѓР ВµР С”...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("Р СљР С•Р Р…Р С‘РЎвЂљР С•РЎР‚Р С‘Р Р…Р С– Р С•РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р В»Р ВµР Р… Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР С")
                break
            except Exception as e:
                logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р Р† РЎвЂ Р С‘Р С”Р В»Р Вµ: {e}", exc_info=True)
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
        Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° РЎвЂЎРЎвЂљР С• РЎвЂћР В°Р в„–Р В» "Р С–Р С•РЎвЂљР С•Р Р†" Р С” Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р Вµ:
        - Р В Р В°Р В·Р СР ВµРЎР‚ > Р СР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…Р С•Р С–Р С•
        - Р СњР Вµ Р СР ВµР Р…РЎРЏР В»РЎРѓРЎРЏ Р С—Р С•РЎРѓР В»Р ВµР Т‘Р Р…Р С‘Р Вµ FILE_STABLE_TIME РЎРѓР ВµР С”РЎС“Р Р…Р Т‘
        - Р СњР Вµ Р В·Р В°Р В±Р В»Р С•Р С”Р С‘РЎР‚Р С•Р Р†Р В°Р Р… Р Т‘РЎР‚РЎС“Р С–Р С‘Р С Р С—РЎР‚Р С•РЎвЂ Р ВµРЎРѓРЎРѓР С•Р С
        """
        try:
            stat = file_path.stat()

            # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° Р СР С‘Р Р…Р С‘Р СР В°Р В»РЎРЉР Р…Р С•Р С–Р С• РЎР‚Р В°Р В·Р СР ВµРЎР‚Р В°
            if stat.st_size < self.MIN_FILE_SIZE:
                logger.debug(f"  РІСњРЉ {file_path.name}: РЎР‚Р В°Р В·Р СР ВµРЎР‚ {stat.st_size} < {self.MIN_FILE_SIZE}")
                return False

            current_time = time.time()
            file_mtime = stat.st_mtime  # РІвЂ С’ Р вЂ™РЎР‚Р ВµР СРЎРЏ Р СР С•Р Т‘Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘Р С‘ РЎвЂћР В°Р в„–Р В»Р В°
            file_size = stat.st_size

            # РІвЂ С’ FIX: Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С РЎРѓРЎвЂљРЎР‚Р С•Р С”Р С•Р Р†РЎвЂ№Р в„– Р С—РЎС“РЎвЂљРЎРЉ Р Т‘Р В»РЎРЏ Р Р…Р В°Р Т‘РЎвЂР В¶Р Р…Р С•РЎРѓРЎвЂљР С‘
            cache_key = str(file_path)

            if cache_key in self._file_cache:
                first_seen_time, cached_mtime, cached_size = self._file_cache[cache_key]

                # Р вЂўРЎРѓР В»Р С‘ РЎР‚Р В°Р В·Р СР ВµРЎР‚ Р С‘Р В»Р С‘ mtime РЎвЂћР В°Р в„–Р В»Р В° Р С‘Р В·Р СР ВµР Р…Р С‘Р В»Р С‘РЎРѓРЎРЉ РІР‚вЂќ РЎвЂћР В°Р в„–Р В» Р ВµРЎвЂ°РЎвЂ Р С—Р С‘РЎв‚¬Р ВµРЎвЂљРЎРѓРЎРЏ
                if file_mtime != cached_mtime or file_size != cached_size:
                    logger.debug(f"  СЂСџвЂќвЂћ {file_path.name}: РЎвЂћР В°Р в„–Р В» Р С‘Р В·Р СР ВµР Р…Р С‘Р В»РЎРѓРЎРЏ, РЎРѓР В±РЎР‚Р С•РЎРѓ Р С”РЎРЊРЎв‚¬Р В°")
                    # РІвЂ С’ FIX: Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµР С Р Р†РЎР‚Р ВµР СРЎРЏ Р С—Р ВµРЎР‚Р Р†Р С•Р С–Р С• Р Р…Р В°Р В±Р В»РЎР‹Р Т‘Р ВµР Р…Р С‘РЎРЏ
                    self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                    return False

                # РІвЂ С’ FIX: Р РЋРЎР‚Р В°Р Р†Р Р…Р С‘Р Р†Р В°Р ВµР С РЎРѓ Р вЂ™Р В Р вЂўР СљР вЂўР СњР вЂўР Сљ Р СџР вЂўР В Р вЂ™Р С›Р вЂњР С› Р СњР С’Р вЂР вЂєР В®Р вЂќР вЂўР СњР ВР Р‡, Р В° Р Р…Р Вµ mtime РЎвЂћР В°Р в„–Р В»Р В°!
                time_since_first_seen = current_time - first_seen_time

                logger.debug(
                    f"  РІРЏВ± {file_path.name}: Р Р…Р В°Р В±Р В»РЎР‹Р Т‘Р В°Р ВµРЎвЂљРЎРѓРЎРЏ {time_since_first_seen:.1f}РЎРѓР ВµР С” (Р Р…РЎС“Р В¶Р Р…Р С• {self.FILE_STABLE_TIME}РЎРѓР ВµР С”)")

                if time_since_first_seen >= self.FILE_STABLE_TIME:
                    logger.debug(f"  РІСљвЂ¦ {file_path.name}: Р вЂњР С›Р СћР С›Р вЂ™ Р С” Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р Вµ!")
                    del self._file_cache[cache_key]
                    return True
                else:
                    return False
            else:
                # РІвЂ С’ FIX: Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С (Р Р†РЎР‚Р ВµР СРЎРЏ_Р Р…Р В°Р В±Р В»РЎР‹Р Т‘Р ВµР Р…Р С‘РЎРЏ, mtime_РЎвЂћР В°Р в„–Р В»Р В°, РЎР‚Р В°Р В·Р СР ВµРЎР‚_РЎвЂћР В°Р в„–Р В»Р В°)
                logger.debug(f"  СЂСџвЂњСњ {file_path.name}: Р С—Р ВµРЎР‚Р Р†Р С•Р Вµ Р Р…Р В°Р В±Р В»РЎР‹Р Т‘Р ВµР Р…Р С‘Р Вµ, Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р Р† Р С”РЎРЊРЎв‚¬")
                self._file_cache[cache_key] = (current_time, file_mtime, file_size)
                return False

        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"  РІС™В  {file_path.name}: Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… ({e})")
            return False
        except Exception as e:
            logger.warning(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р С‘ Р С–Р С•РЎвЂљР С•Р Р†Р Р…Р С•РЎРѓРЎвЂљР С‘ РЎвЂћР В°Р в„–Р В»Р В° {file_path}: {e}")
            return False

    def check_for_new_files(self):
        """Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° Р Р…Р С•Р Р†РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р Р†Р С• Р Р†Р Р…Р ВµРЎв‚¬Р Р…Р ВµР в„– Р С—Р В°Р С—Р С”Р Вµ."""
        logger.debug("СЂСџвЂќРЊ check_for_new_files: Р СњР С’Р В§Р С’Р вЂєР С›")

        if not self.external_path.exists():
            logger.warning(f"Р вЂ™Р Р…Р ВµРЎв‚¬Р Р…РЎРЏРЎРЏ Р С—Р В°Р С—Р С”Р В° Р Р…Р Вµ РЎРѓРЎС“РЎвЂ°Р ВµРЎРѓРЎвЂљР Р†РЎС“Р ВµРЎвЂљ: {self.external_path}")
            return

        logger.debug(f"СЂСџвЂњвЂљ Р РЋР С”Р В°Р Р…Р С‘РЎР‚РЎС“Р ВµР С: {self.external_path}")

        files_count = 0
        for item in self.external_path.iterdir():
            files_count += 1
            logger.debug(f"  [{files_count}] {item.name} (file={item.is_file()})")

            if item.is_file() and not item.name.startswith('.'):
                logger.debug(f"    РІвЂ вЂ™ Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С Р С–Р С•РЎвЂљР С•Р Р†Р Р…Р С•РЎРѓРЎвЂљРЎРЉ: {item.name}")

                if not self._is_file_ready(item):
                    logger.debug(f"    РІвЂ вЂ™ Р В¤Р В°Р в„–Р В» Р Р…Р Вµ Р С–Р С•РЎвЂљР С•Р Р†, Р С—РЎР‚Р С•Р С—РЎС“РЎРѓР С”Р В°Р ВµР С")
                    continue

                logger.debug(f"    РІвЂ вЂ™ Р В¤Р В°Р в„–Р В» Р С–Р С•РЎвЂљР С•Р Р†! Р С›Р В±РЎР‚Р В°Р В±Р В°РЎвЂљРЎвЂ№Р Р†Р В°Р ВµР С...")

                file_stat = item.stat()
                cache_key = f"{item.name}:{file_stat.st_mtime}:{file_stat.st_size}"
                persistent_key = self._build_persistent_fingerprint(item, file_stat)

                if persistent_key in self.processed_index:
                    storage_dir = self.processed_index[persistent_key].get("storage_dir", "unknown")
                    logger.info(f"Skipping already imported file: {item.name} -> {storage_dir}")
                    self.processed_files.add(cache_key)
                    continue

                existing_storage = self._find_existing_import(item, file_stat)
                if existing_storage:
                    logger.info(f"Skipping file already present in shared storage: {item.name} -> {existing_storage}")
                    self.processed_files.add(cache_key)
                    self._remember_processed_file(item, file_stat, file_id="existing", storage_dir=existing_storage)
                    continue

                if cache_key not in self.processed_files:
                    logger.info(f"Р С›Р В±Р Р…Р В°РЎР‚РЎС“Р В¶Р ВµР Р… Р Р…Р С•Р Р†РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В»: {item.name} ({file_stat.st_size} Р В±Р В°Р в„–РЎвЂљ)")
                    file_id = str(uuid.uuid4())[:8]
                    success = self.process_new_file(item, file_id)

                    if success:
                        self.processed_files.add(cache_key)
                        if len(self.processed_files) > 1000:
                            self.processed_files = set(list(self.processed_files)[-1000:])
                    else:
                        logger.warning(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР В°РЎвЂљРЎРЉ РЎвЂћР В°Р в„–Р В» {item.name}")
                else:
                    logger.debug(f"    РІвЂ вЂ™ Р В¤Р В°Р в„–Р В» РЎС“Р В¶Р Вµ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р Р… (Р Р† Р С”РЎРЊРЎв‚¬Р Вµ)")

        logger.debug(f"РІСљвЂ¦ check_for_new_files: Р вЂ”Р С’Р вЂ™Р вЂўР В Р РЃР вЂўР СњР С› (РЎвЂћР В°Р в„–Р В»Р С•Р Р†: {files_count})")

    def process_new_file(self, file_path: Path, file_id: str) -> bool:
        """
        Р С›Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° Р Р…Р С•Р Р†Р С•Р С–Р С• РЎвЂћР В°Р в„–Р В»Р В°: РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ№ Р С‘ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р С”Р В° Р Р† Р С•РЎвЂЎР ВµРЎР‚Р ВµР Т‘РЎРЉ.

        Returns:
            True Р ВµРЎРѓР В»Р С‘ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р В°, False Р ВµРЎРѓР В»Р С‘ Р С—РЎР‚Р С•Р С‘Р В·Р С•РЎв‚¬Р В»Р В° Р С•РЎв‚¬Р С‘Р В±Р С”Р В°
        """
        try:
            # РІвЂ С’ FIX: Р РЋР С•Р В·Р Т‘Р В°РЎвЂР С РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎС“ РЎРѓ РЎРЏР Р†Р Р…РЎвЂ№Р СР С‘ Р С—РЎР‚Р В°Р Р†Р В°Р СР С‘
            stem = Path(file_path.name).stem
            storage_dir = stem
            suffix = 2
            while (self.shared_path / storage_dir).exists():
                storage_dir = f"{stem}__{suffix}"
                suffix += 1
            base_dir = self.shared_path / storage_dir
            original_dir = base_dir / "original"
            safe_mkdir(original_dir, mode=0o755)

            # Р С™Р С•Р С—Р С‘РЎР‚РЎС“Р ВµР С РЎвЂћР В°Р в„–Р В» РЎРѓ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р…Р С‘Р ВµР С Р СР ВµРЎвЂљР В°Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦
            dest_path = original_dir / file_path.name

            # РІвЂ С’ FIX: Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° РЎвЂЎРЎвЂљР С• РЎвЂћР В°Р в„–Р В» Р ВµРЎвЂ°РЎвЂ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р С—Р ВµРЎР‚Р ВµР Т‘ Р С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р ВµР С
            if not file_path.exists():
                logger.warning(f"Р В¤Р В°Р в„–Р В» Р С‘РЎРѓРЎвЂЎР ВµР В· Р С—Р ВµРЎР‚Р ВµР Т‘ Р С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р ВµР С: {file_path}")
                return False

            shutil.copy2(file_path, dest_path)
            source_stat = file_path.stat()

            # РІвЂ С’ FIX: Р Р‡Р Р†Р Р…Р С• РЎС“РЎРѓРЎвЂљР В°Р Р…Р В°Р Р†Р В»Р С‘Р Р†Р В°Р ВµР С Р С—РЎР‚Р В°Р Р†Р В° Р Р…Р В° РЎРѓР С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р Р…РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В»
            try:
                os.chmod(dest_path, 0o644)  # Р В§РЎвЂљР ВµР Р…Р С‘Р Вµ Р Т‘Р В»РЎРЏ Р Р†РЎРѓР ВµРЎвЂ¦, Р В·Р В°Р С—Р С‘РЎРѓРЎРЉ Р Т‘Р В»РЎРЏ Р Р†Р В»Р В°Р Т‘Р ВµР В»РЎРЉРЎвЂ Р В°
            except PermissionError:
                logger.warning(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РЎС“РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р С‘РЎвЂљРЎРЉ Р С—РЎР‚Р В°Р Р†Р В° Р Р…Р В° {dest_path}")

            logger.info(f"Р В¤Р В°Р в„–Р В» РЎРѓР С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…: {file_path} РІвЂ вЂ™ {dest_path}")

            # Р РЋР С•Р В·Р Т‘Р В°РЎвЂР С FileJob
            file_type = FileJob.detect_file_type(file_path.name)
            file_size = file_path.stat().st_size

            job = FileJob(
                file_id=file_id,
                original_filename=file_path.name,
                storage_dir=storage_dir,
                file_type=file_type,
                file_size=file_size,
                status=FileStatus.UPLOADED,
                current_module="cleaner",
                export_to_1c=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р Р† Redis
            self.redis.set_file_status(file_id, job.to_dict())

            # Р С›РЎвЂљР С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµР С Р Р† Р С•РЎвЂЎР ВµРЎР‚Р ВµР Т‘РЎРЉ preprocess
            self.redis.push_to_queue("files:cleaner", job.to_payload(), priority=job.priority)

            # Р СџРЎС“Р В±Р В»Р С‘Р С”РЎС“Р ВµР С РЎРѓР С•Р В±РЎвЂ№РЎвЂљР С‘Р Вµ Р Т‘Р В»РЎРЏ UI
            self.redis.publish_event("files:events", {
                "type": "file_uploaded",
                "file_id": file_id,
                "filename": file_path.name,
                "status": job.status.value,
                "file_type": file_type.value,
                "file_size": file_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"Р В¤Р В°Р в„–Р В» {file_id} Р Т‘Р С•Р В±Р В°Р Р†Р В»Р ВµР Р… Р Р† Р С•РЎвЂЎР ВµРЎР‚Р ВµР Т‘РЎРЉ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘")
            self._remember_processed_file(file_path, source_stat, file_id=file_id, storage_dir=storage_dir)
            return True

        except PermissionError as e:
            logger.error(f"РІСњРЉ Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р В°Р Р† Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р В° Р С—РЎР‚Р С‘ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р Вµ {file_path}: {e}")
            logger.error(f"СЂСџвЂ™РЋ Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЉРЎвЂљР Вµ Р С—РЎР‚Р В°Р Р†Р В°: ls -la {file_path.parent}")
            self._publish_error_event(file_path.name, f"PermissionError: {e}")
            return False

        except shutil.Error as e:
            logger.error(f"РІСњРЉ Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С”Р С•Р С—Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ {file_path}: {e}")
            self._publish_error_event(file_path.name, f"CopyError: {e}")
            return False

        except Exception as e:
            logger.error(f"РІСњРЉ Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘ РЎвЂћР В°Р в„–Р В»Р В° {file_path}: {e}", exc_info=True)
            self._publish_error_event(file_path.name, str(e))
            return False

    def _publish_error_event(self, filename: str, error: str):
        """Р СџРЎС“Р В±Р В»Р С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ РЎРѓР С•Р В±РЎвЂ№РЎвЂљР С‘РЎРЏ Р С•Р В± Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ Р Т‘Р В»РЎРЏ UI."""
        try:
            self.redis.publish_event("files:events", {
                "type": "file_error",
                "filename": filename,
                "error": error,
                # РІвЂ С’ FIX: timezone-aware timestamp
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С•Р С—РЎС“Р В±Р В»Р С‘Р С”Р С•Р Р†Р В°РЎвЂљРЎРЉ РЎРѓР С•Р В±РЎвЂ№РЎвЂљР С‘Р Вµ Р С•Р В± Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ: {e}")

    def cleanup_cache(self):
        """Р С›РЎвЂЎР С‘РЎРѓРЎвЂљР С”Р В° Р С”РЎРЊРЎв‚¬Р В° Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р† (Р Т‘Р В»РЎРЏ Р С—РЎР‚Р ВµР Т‘Р С•РЎвЂљР Р†РЎР‚Р В°РЎвЂ°Р ВµР Р…Р С‘РЎРЏ РЎС“РЎвЂљР ВµРЎвЂЎР ВµР С” Р С—Р В°Р СРЎРЏРЎвЂљР С‘)."""
        # Р С›РЎРѓРЎвЂљР В°Р Р†Р В»РЎРЏР ВµР С РЎвЂљР С•Р В»РЎРЉР С”Р С• Р С—Р С•РЎРѓР В»Р ВµР Т‘Р Р…Р С‘Р Вµ 500 Р В·Р В°Р С—Р С‘РЎРѓР ВµР в„–
        if len(self.processed_files) > 500:
            old_count = len(self.processed_files)
            self.processed_files = set(list(self.processed_files)[-500:])
            logger.debug(f"Р С™РЎРЊРЎв‚¬ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р С•РЎвЂЎР С‘РЎвЂ°Р ВµР Р…: {old_count} РІвЂ вЂ™ {len(self.processed_files)}")


def main():
    """Р СћР С•РЎвЂЎР С”Р В° Р Р†РЎвЂ¦Р С•Р Т‘Р В° Р Т‘Р В»РЎРЏ Р С”Р С•Р Р…РЎвЂљР ВµР в„–Р Р…Р ВµРЎР‚Р В° monitor."""
    logger.info("Р вЂ”Р В°Р С—РЎС“РЎРѓР С” FileMonitor...")

    try:
        monitor = FileMonitor()
        monitor.start()
    except Exception as e:
        logger.error(f"Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
