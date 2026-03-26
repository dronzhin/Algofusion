# core/services/file_service.py
"""
Р РЋР ВµРЎР‚Р Р†Р С‘РЎРѓ Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂ№ РЎРѓ РЎвЂћР В°Р в„–Р В»Р В°Р СР С‘.
Р С›Р В±РЎвЂ°Р В°РЎРЏ Р В»Р С•Р С–Р С‘Р С”Р В° Р Т‘Р В»РЎРЏ Р Р†РЎРѓР ВµРЎвЂ¦ Р С”Р С•Р Р…РЎвЂљР ВµР в„–Р Р…Р ВµРЎР‚Р С•Р Р†.
"""

import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone  # РІвЂ С’ Р вЂќР С•Р В±Р В°Р Р†Р С‘Р В»Р С‘ timezone
from shared.models.file import FileJob
from shared.utils.logger import setup_logger
from shared.utils.helpers import safe_mkdir

logger = setup_logger("core.services.file_service")


class FileService:
    """Р РЋР ВµРЎР‚Р Р†Р С‘РЎРѓ Р Т‘Р В»РЎРЏ РЎС“Р С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ РЎвЂћР В°Р в„–Р В»Р В°Р СР С‘ Р С‘ Р С—Р В°Р С—Р С”Р В°Р СР С‘."""

    def __init__(self, base_dir: str = "/shared/files"):
        self.base_dir = Path(base_dir)
        safe_mkdir(self.base_dir)
        logger.info(f"FileService Р С‘Р Р…Р С‘РЎвЂ Р С‘Р В°Р В»Р С‘Р В·Р С‘РЎР‚Р С•Р Р†Р В°Р Р…: base_dir={self.base_dir}")

    def create_file_structure(self, file_job: FileJob) -> bool:
        """Р РЋР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ№ Р С—Р В°Р С—Р С•Р С” Р Т‘Р В»РЎРЏ РЎвЂћР В°Р в„–Р В»Р В°."""
        try:
            base = file_job.get_base_path(str(self.base_dir))

            directories = [
                base / "original",
                base / "preprocessed",
                base / "ocr",
                base / "llm",
                base / "export",
                base / "archive"
            ]

            for dir_path in directories:
                safe_mkdir(dir_path)

            logger.info(f"Р РЋРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚Р В° Р С—Р В°Р С—Р С•Р С” РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р В° Р Т‘Р В»РЎРЏ РЎвЂћР В°Р в„–Р В»Р В° {file_job.file_id}")
            return True
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ№ Р С—Р В°Р С—Р С•Р С”: {e}", exc_info=True)
            return False

    def move_to_archive(self, file_job: FileJob) -> bool:
        """Р СџР ВµРЎР‚Р ВµР СР ВµРЎвЂ°Р ВµР Р…Р С‘Р Вµ РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р Р† Р В°РЎР‚РЎвЂ¦Р С‘Р Р† Р С—Р С•РЎРѓР В»Р Вµ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘."""
        try:
            base = file_job.get_base_path(str(self.base_dir))
            archive_path = file_job.get_archive_path(str(self.base_dir))

            # Р РЋР С•Р В·Р Т‘Р В°РЎвЂР С ZIP Р В°РЎР‚РЎвЂ¦Р С‘Р Р†
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for folder in ["original", "preprocessed", "ocr", "llm", "export"]:
                    folder_path = base / folder
                    if folder_path.exists():
                        for file_path in folder_path.rglob("*"):
                            if file_path.is_file():
                                arcname = file_path.relative_to(base)
                                zipf.write(file_path, arcname)

            logger.info(f"Р В¤Р В°Р в„–Р В» {file_job.file_id} Р В°РЎР‚РЎвЂ¦Р С‘Р Р†Р С‘РЎР‚Р С•Р Р†Р В°Р Р…: {archive_path}")
            return True
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р В°РЎР‚РЎвЂ¦Р С‘Р Р†Р В°РЎвЂ Р С‘Р С‘ РЎвЂћР В°Р в„–Р В»Р В° {file_job.file_id}: {e}", exc_info=True)
            return False
    def get_file_info(self, file_id: str, original_filename: Optional[str] = None, storage_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Р В РЎСџР В РЎвЂўР В Р’В»Р РЋРЎвЂњР РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В РЎвЂР В Р’Вµ Р В РЎвЂР В Р вЂ¦Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р РЋРІР‚В Р В РЎвЂР В РЎвЂ Р В РЎвЂў Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’Вµ."""
        try:
            if storage_dir:
                base = self.base_dir / storage_dir
            elif original_filename:
                base = self.base_dir / Path(original_filename).stem
            else:
                base = self.base_dir / file_id
            if not base.exists():
                base = self.base_dir / file_id
            if not base.exists():
                return None

            info = {
                "file_id": file_id,
                "base_path": str(base),
                "directories": {}
            }

            for folder in ["original", "preprocessed", "ocr", "llm", "export", "archive"]:
                folder_path = base / folder
                if folder_path.exists():
                    files = list(folder_path.rglob("*"))
                    info["directories"][folder] = {
                        "path": str(folder_path),
                        "file_count": len([f for f in files if f.is_file()]),
                        "files": [f.name for f in files if f.is_file()]
                    }

            return info
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С‘Р Р…РЎвЂћР С•РЎР‚Р СР В°РЎвЂ Р С‘Р С‘ Р С• РЎвЂћР В°Р в„–Р В»Р Вµ {file_id}: {e}", exc_info=True)
            return None

    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """Р С›РЎвЂЎР С‘РЎРѓРЎвЂљР С”Р В° РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р†."""
        try:
            cleaned = 0
            # РІвЂ С’ Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С timezone-aware datetime
            now = datetime.now(timezone.utc)

            for file_dir in self.base_dir.iterdir():
                if file_dir.is_dir() and file_dir.name != "archive":
                    # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С Р Р†РЎР‚Р ВµР СРЎРЏ РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ РЎРѓ РЎвЂљР В°Р в„–Р СР В·Р С•Р Р…Р С•Р в„–
                    created = datetime.fromtimestamp(
                        file_dir.stat().st_ctime,
                        tz=timezone.utc  # РІвЂ С’ Р Р€Р С”Р В°Р В·РЎвЂ№Р Р†Р В°Р ВµР С РЎвЂљР В°Р в„–Р СР В·Р С•Р Р…РЎС“ РЎРЏР Р†Р Р…Р С•
                    )
                    age = (now - created).days

                    if age > max_age_days:
                        shutil.rmtree(file_dir)
                        cleaned += 1
                        logger.info(f"Р Р€Р Т‘Р В°Р В»РЎвЂР Р… РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В»: {file_dir.name} ({age} Р Т‘Р Р…Р ВµР в„–)")

            logger.info(f"Р С›РЎвЂЎР С‘РЎРѓРЎвЂљР С”Р В° Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р ВµР Р…Р В°: РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С• {cleaned} РЎвЂћР В°Р в„–Р В»Р С•Р Р†")
            return cleaned
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С•РЎвЂЎР С‘РЎРѓРЎвЂљР С”Р С‘ РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№РЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р†: {e}", exc_info=True)
            return 0

    def list_files(self) -> List[str]:
        """Р РЋР С—Р С‘РЎРѓР С•Р С” Р Р†РЎРѓР ВµРЎвЂ¦ РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р Р† Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р Вµ."""
        try:
            return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓР С—Р С‘РЎРѓР С”Р В° РЎвЂћР В°Р в„–Р В»Р С•Р Р†: {e}")
            return []
