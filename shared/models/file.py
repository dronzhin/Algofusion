# shared/models/file.py
"""
Р СљР С•Р Т‘Р ВµР В»РЎРЉ РЎвЂћР В°Р в„–Р В»Р В° Р Т‘Р В»РЎРЏ Р С•Р В±Р СР ВµР Р…Р В° Р СР ВµР В¶Р Т‘РЎС“ Р СР С•Р Т‘РЎС“Р В»РЎРЏР СР С‘.
Р вЂўР Т‘Р С‘Р Р…Р В°РЎРЏ Р СР С•Р Т‘Р ВµР В»РЎРЉ Р Т‘Р В»РЎРЏ UI, Workers Р С‘ Monitor.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json

from shared.utils.logger import setup_logger

logger = setup_logger("shared.models.file")


class FileType(str, Enum):
    """Р СћР С‘Р С—РЎвЂ№ РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р Т‘Р В»РЎРЏ Р СР В°РЎР‚РЎв‚¬РЎР‚РЎС“РЎвЂљР С‘Р В·Р В°РЎвЂ Р С‘Р С‘."""
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileStatus(str, Enum):
    """Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘ РЎвЂћР В°Р в„–Р В»Р В°."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


class ExportStatus(str, Enum):
    """Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ РЎРЊР С”РЎРѓР С—Р С•РЎР‚РЎвЂљР В° Р Р† 1Р РЋ."""
    PENDING = "pending"
    EXPORTING = "exporting"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ExportConfig:
    """Р С™Р С•Р Р…РЎвЂћР С‘Р С–РЎС“РЎР‚Р В°РЎвЂ Р С‘РЎРЏ РЎРЊР С”РЎРѓР С—Р С•РЎР‚РЎвЂљР В° Р Р† 1Р РЋ."""
    enabled: bool = False
    mode: str = "manual"  # manual, auto, batch
    format: str = "1c_xml"
    endpoint: str = ""
    batch_size: int = 10
    retry_count: int = 3


@dataclass
class FileJob:
    """Р СљР С•Р Т‘Р ВµР В»РЎРЉ Р В·Р В°Р Т‘Р В°Р Р…Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘ РЎвЂћР В°Р в„–Р В»Р В°."""

    file_id: str
    original_filename: str
    storage_dir: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    file_size: int = 0
    status: FileStatus = FileStatus.UPLOADED

    current_module: Optional[str] = None
    completed_modules: Set[str] = field(default_factory=set)

    ocr_engine: str = "tesseract"
    ocr_lang: str = "rus+eng"

    export_to_1c: bool = False
    export_config: ExportConfig = field(default_factory=ExportConfig)
    export_status: ExportStatus = ExportStatus.PENDING
    export_attempts: int = 0
    export_error: Optional[str] = None
    exported_at: Optional[datetime] = None
    document_1c_id: Optional[str] = None

    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: str) -> "FileJob":
        """Р РЋР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ FileJob Р С‘Р В· JSON payload."""
        try:
            data = json.loads(payload)
            logger.debug(f"Р РЋР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ FileJob Р С‘Р В· payload: file_id={data.get('file_id')}")

            file_type = FileType(data.get("file_type", "unknown"))
            status = FileStatus(data.get("status", "uploaded"))
            export_status = ExportStatus(data.get("export_status", "pending"))

            completed = data.get("completed_modules", [])
            if isinstance(completed, list):
                completed = set(completed)

            export_config_data = data.get("export_config", {})
            export_config = ExportConfig(**export_config_data) if export_config_data else ExportConfig()

            # РІвЂ С’ FIX: Р СџР В°РЎР‚РЎРѓР С‘Р Р…Р С– datetime РЎРѓ Р С—Р С•Р Т‘Р Т‘Р ВµРЎР‚Р В¶Р С”Р С•Р в„– timezone
            exported_at = None
            if data.get("exported_at"):
                exported_at = cls._parse_datetime(data["exported_at"])

            return cls(
                file_id=data.get("file_id", "unknown"),
                original_filename=data.get("original_filename", "unknown"),
                storage_dir=data.get("storage_dir"),
                file_type=file_type,
                file_size=data.get("file_size", 0),
                status=status,
                current_module=data.get("current_module"),
                completed_modules=completed,
                ocr_engine=data.get("ocr_engine", "tesseract"),
                ocr_lang=data.get("ocr_lang", "rus+eng"),
                export_to_1c=data.get("export_to_1c", False),
                export_config=export_config,
                export_status=export_status,
                export_attempts=data.get("export_attempts", 0),
                export_error=data.get("export_error"),
                exported_at=exported_at,
                document_1c_id=data.get("document_1c_id"),
                config=data.get("config", {}),
                priority=data.get("priority", 0),
                callback_url=data.get("callback_url"),
                metadata=data.get("metadata", {}),
                retry_count=data.get("retry_count", 0),
                max_retries=data.get("max_retries", 3),
                history=data.get("history", []),
                errors=data.get("errors", [])
            )
        except Exception as e:
            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р В°РЎР‚РЎРѓР С‘Р Р…Р С–Р В° payload: {e}", exc_info=True)
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Р С™Р С•Р Р…Р Р†Р ВµРЎР‚РЎвЂљР В°РЎвЂ Р С‘РЎРЏ Р Р† РЎРѓР В»Р С•Р Р†Р В°РЎР‚РЎРЉ."""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "storage_dir": self.storage_dir,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "status": self.status.value,
            "current_module": self.current_module,
            "completed_modules": list(self.completed_modules),
            "ocr_engine": self.ocr_engine,
            "ocr_lang": self.ocr_lang,
            "export_to_1c": self.export_to_1c,
            "export_config": {
                "enabled": self.export_config.enabled,
                "mode": self.export_config.mode,
                "format": self.export_config.format,
                "endpoint": self.export_config.endpoint,
                "batch_size": self.export_config.batch_size
            },
            "export_status": self.export_status.value,
            "export_attempts": self.export_attempts,
            "export_error": self.export_error,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "document_1c_id": self.document_1c_id,
            "config": self.config,
            "priority": self.priority,
            "callback_url": self.callback_url,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "history": self.history,
            "errors": self.errors
        }

    def to_payload(self) -> str:
        """Р РЋР ВµРЎР‚Р С‘Р В°Р В»Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р С”Р С‘ Р Р† Р С•РЎвЂЎР ВµРЎР‚Р ВµР Т‘РЎРЉ."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    def get_storage_dir_name(self) -> str:
        if self.storage_dir:
            return self.storage_dir
        return Path(self.original_filename).stem


    def get_base_path(self, base_dir: str = "/shared/files") -> Path:
        """Base directory for this file."""
        base_dir_path = Path(base_dir)
        preferred = base_dir_path / self.get_storage_dir_name()
        legacy = base_dir_path / self.file_id
        if legacy.exists() and not preferred.exists():
            return legacy
        return preferred

    def get_original_path(self, base_dir: str = "/shared/files") -> Path:
        """Р СџРЎС“РЎвЂљРЎРЉ Р С” Р С•РЎР‚Р С‘Р С–Р С‘Р Р…Р В°Р В»РЎРЉР Р…Р С•Р СРЎС“ РЎвЂћР В°Р в„–Р В»РЎС“."""
        return self.get_base_path(base_dir) / "original" / self.original_filename

    def get_module_input_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        """Р СџРЎС“РЎвЂљРЎРЉ Р С” Р Р†РЎвЂ¦Р С•Р Т‘Р Р…Р С•Р СРЎС“ РЎвЂћР В°Р в„–Р В»РЎС“ Р Т‘Р В»РЎРЏ Р СР С•Р Т‘РЎС“Р В»РЎРЏ."""
        base = self.get_base_path(base_dir)

        if module == "cleaner":
            return self.get_original_path(base_dir)
        elif module == "ocr":
            preprocessed = base / "preprocessed" / self.original_filename
            if preprocessed.exists():
                return preprocessed
            return self.get_original_path(base_dir)
        elif module == "llm":
            return base / "ocr" / f"{Path(self.original_filename).stem}.txt"
        elif module == "export":
            return base / "llm" / "analysis.json"

        return self.get_original_path(base_dir)

    def get_module_output_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        """Р СџРЎС“РЎвЂљРЎРЉ Р Т‘Р В»РЎРЏ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР В° Р СР С•Р Т‘РЎС“Р В»РЎРЏ."""
        base = self.get_base_path(base_dir) / module
        base.mkdir(parents=True, exist_ok=True)

        if module == "ocr":
            return base / f"{Path(self.original_filename).stem}.txt"
        elif module == "llm":
            return base / "analysis.json"
        elif module == "export":
            return base / f"{Path(self.original_filename).stem}_1c.xml"

        return base / self.original_filename

    def get_export_path(self, base_dir: str = "/shared/files") -> Path:
        """Р СџРЎС“РЎвЂљРЎРЉ Р Т‘Р В»РЎРЏ XML РЎРЊР С”РЎРѓР С—Р С•РЎР‚РЎвЂљР В°."""
        export_dir = self.get_base_path(base_dir) / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        name = Path(self.original_filename).stem
        return export_dir / f"{name}_1c.xml"

    def get_archive_path(self, base_dir: str = "/shared/files") -> Path:
        """Р СџРЎС“РЎвЂљРЎРЉ Р Т‘Р В»РЎРЏ Р В°РЎР‚РЎвЂ¦Р С‘Р Р†Р В° Р С—Р С•РЎРѓР В»Р Вµ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘."""
        archive_dir = self.get_base_path(base_dir) / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir / f"{self.file_id}_processed.zip"

    @classmethod
    def detect_file_type(cls, filename: str) -> FileType:
        """Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р Вµ РЎвЂљР С‘Р С—Р В° РЎвЂћР В°Р в„–Р В»Р В° Р С—Р С• РЎР‚Р В°РЎРѓРЎв‚¬Р С‘РЎР‚Р ВµР Р…Р С‘РЎР‹."""
        ext = Path(filename).suffix.lower()
        extensions = {
            FileType.IMAGE: {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"},
            FileType.PDF: {".pdf"},
            FileType.DOCUMENT: {".doc", ".docx", ".odt", ".rtf"},
            FileType.TEXT: {".txt", ".md", ".csv", ".json", ".xml"},
        }
        for file_type, exts in extensions.items():
            if ext in exts:
                return file_type
        return FileType.UNKNOWN

    def get_allowed_modules(self) -> List[str]:
        """Р СџР С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ РЎРѓР С—Р С‘РЎРѓР С•Р С” Р СР С•Р Т‘РЎС“Р В»Р ВµР в„– Р Т‘Р В»РЎРЏ РЎРЊРЎвЂљР С•Р С–Р С• РЎвЂљР С‘Р С—Р В° РЎвЂћР В°Р в„–Р В»Р В°."""
        routing = {
            FileType.IMAGE: ["cleaner", "layout", "ocr", "parser", "normalizer", "reconcile", "final_json"],
            FileType.PDF: ["cleaner", "layout", "ocr", "parser", "normalizer", "reconcile", "final_json"],
            FileType.DOCUMENT: [],
            FileType.TEXT: [],
            FileType.UNKNOWN: [],
        }
        return routing.get(self.file_type, [])

    def complete_module(self, module: str):
        """Р вЂ”Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘РЎвЂљРЎРЉ Р СР С•Р Т‘РЎС“Р В»РЎРЉ."""
        self.completed_modules.add(module)
        self.current_module = None
        self.updated_at = datetime.now(timezone.utc)
        logger.debug(f"Р СљР С•Р Т‘РЎС“Р В»РЎРЉ {module} Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬РЎвЂР Р… Р Т‘Р В»РЎРЏ РЎвЂћР В°Р в„–Р В»Р В° {self.file_id}")

    def add_to_history(self, action: str, module: str, success: bool,
                       error: str = None, duration: float = None):
        """Р вЂќР С•Р В±Р В°Р Р†Р С‘РЎвЂљРЎРЉ Р В·Р В°Р С—Р С‘РЎРѓРЎРЉ Р Р† Р С‘РЎРѓРЎвЂљР С•РЎР‚Р С‘РЎР‹."""
        # РІвЂ С’ FIX: timezone-aware datetime
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module": module,
            "action": action,
            "success": success,
            "error": error,
            "duration_seconds": duration
        })
        self.updated_at = datetime.now(timezone.utc)

    def is_complete(self) -> bool:
        """Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р ВµР Р…Р В° Р В»Р С‘ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В°."""
        if self.status == FileStatus.FAILED:
            return True
        allowed = self.get_allowed_modules()
        return all(m in self.completed_modules for m in allowed)

    def can_retry(self) -> bool:
        """Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ Р СР С•Р В¶Р Р…Р С• Р В»Р С‘ Р С—Р С•Р Р†РЎвЂљР С•РЎР‚Р С‘РЎвЂљРЎРЉ Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”РЎС“."""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """Р Р€Р Р†Р ВµР В»Р С‘РЎвЂЎР С‘РЎвЂљРЎРЉ РЎРѓРЎвЂЎРЎвЂРЎвЂљРЎвЂЎР С‘Р С” Р С—Р С•Р С—РЎвЂ№РЎвЂљР С•Р С”."""
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)
        logger.warning(f"Р СџР С•Р С—РЎвЂ№РЎвЂљР С”Р В° {self.retry_count}/{self.max_retries} Р Т‘Р В»РЎРЏ РЎвЂћР В°Р в„–Р В»Р В° {self.file_id}")

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """
        Р СџР В°РЎР‚РЎРѓР С‘РЎвЂљ ISO-РЎРѓРЎвЂљРЎР‚Р С•Р С”РЎС“ Р Р† datetime, Р С•Р В±Р ВµРЎРѓР С—Р ВµРЎвЂЎР С‘Р Р†Р В°РЎРЏ timezone-aware РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ.
        Р вЂўРЎРѓР В»Р С‘ РЎРѓРЎвЂљРЎР‚Р С•Р С”Р В° Р В±Р ВµР В· РЎвЂљР В°Р в„–Р СР В·Р С•Р Р…РЎвЂ№ РІР‚вЂќ Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ UTC.
        """
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            # Naive datetime РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С Р В·Р В° UTC Р Т‘Р В»РЎРЏ Р С”Р С•Р Р…РЎРѓР С‘РЎРѓРЎвЂљР ВµР Р…РЎвЂљР Р…Р С•РЎРѓРЎвЂљР С‘
            return dt.replace(tzinfo=timezone.utc)
        return dt
