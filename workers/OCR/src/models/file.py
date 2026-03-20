# workers/ocr/src/models/file.py
"""Модель файла для обмена между модулями."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
from pathlib import Path
import json


class FileType(str, Enum):
    """Типы файлов для маршрутизации."""
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileStatus(str, Enum):
    """Статус обработки файла."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


class ExportStatus(str, Enum):
    """Статус экспорта в 1С."""
    PENDING = "pending"
    EXPORTING = "exporting"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ExportConfig:
    """Конфигурация экспорта в 1С."""
    enabled: bool = False
    mode: str = "manual"
    format: str = "1c_xml"
    endpoint: str = ""
    batch_size: int = 10
    retry_count: int = 3


@dataclass
class FileJob:
    """Модель задания для обработки файла."""

    file_id: str
    original_filename: str
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
    document_1c_id: Optional[str] = None  # ← Исправлено: document_1c_id вместо 1c_document_id

    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: str) -> "FileJob":
        """Создание FileJob из JSON payload."""
        data = json.loads(payload)

        file_type = FileType(data.get("file_type", "unknown"))
        status = FileStatus(data.get("status", "uploaded"))
        export_status = ExportStatus(data.get("export_status", "pending"))

        completed = data.get("completed_modules", [])
        if isinstance(completed, list):
            completed = set(completed)

        export_config_data = data.get("export_config", {})
        export_config = ExportConfig(**export_config_data) if export_config_data else ExportConfig()

        return cls(
            file_id=data.get("file_id", "unknown"),
            original_filename=data.get("original_filename", "unknown"),
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
            exported_at=datetime.fromisoformat(data["exported_at"]) if data.get("exported_at") else None,
            document_1c_id=data.get("document_1c_id"),  # ← Исправлено
            config=data.get("config", {}),
            priority=data.get("priority", 0),
            callback_url=data.get("callback_url"),
            metadata=data.get("metadata", {}),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            history=data.get("history", []),
            errors=data.get("errors", [])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
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
            "document_1c_id": self.document_1c_id,  # ← Исправлено
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
        """Сериализация для отправки в очередь."""
        return json.dumps(self.to_dict())

    def get_base_path(self, base_dir: str = "/shared/files") -> Path:
        """Базовая папка для этого файла."""
        return Path(base_dir) / self.file_id

    def get_original_path(self, base_dir: str = "/shared/files") -> Path:
        """Путь к оригинальному файлу."""
        return self.get_base_path(base_dir) / "original" / self.original_filename

    def get_module_input_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        """Путь к входному файлу для модуля."""
        if module == "preprocess":
            return self.get_original_path(base_dir)
        elif module == "ocr":
            preprocessed = self.get_base_path(base_dir) / "preprocessed" / self.original_filename
            if preprocessed.exists():
                return preprocessed
            return self.get_original_path(base_dir)
        elif module == "llm":
            return self.get_base_path(base_dir) / "ocr" / f"{Path(self.original_filename).stem}.txt"
        return self.get_original_path(base_dir)

    def get_module_output_path(self, module: str, base_dir: str = "/shared/files") -> Path:
        """Путь для результата модуля."""
        base = self.get_base_path(base_dir) / module
        base.mkdir(parents=True, exist_ok=True)

        if module == "ocr":
            return base / f"{Path(self.original_filename).stem}.txt"
        elif module == "llm":
            return base / "analysis.json"
        return base / self.original_filename

    def get_export_path(self, base_dir: str = "/shared/files") -> Path:
        """Путь для XML экспорта."""
        export_dir = self.get_base_path(base_dir) / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        name = Path(self.original_filename).stem
        return export_dir / f"{name}_1c.xml"

    @classmethod
    def detect_file_type(cls, filename: str) -> FileType:
        """Определение типа файла по расширению."""
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
        """Получить список модулей для этого типа файла."""
        routing = {
            FileType.IMAGE: ["preprocess", "ocr", "llm"],
            FileType.PDF: ["preprocess", "ocr", "llm"],
            FileType.DOCUMENT: ["preprocess", "llm"],
            FileType.TEXT: ["llm"],
            FileType.UNKNOWN: [],
        }
        return routing.get(self.file_type, [])

    def complete_module(self, module: str):
        """Завершить модуль."""
        self.completed_modules.add(module)
        self.current_module = None
        self.updated_at = datetime.utcnow()

    def add_to_history(self, action: str, module: str, success: bool,
                       error: str = None, duration: float = None):
        """Добавить запись в историю."""
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "module": module,
            "action": action,
            "success": success,
            "error": error,
            "duration_seconds": duration
        })
        self.updated_at = datetime.utcnow()

    def is_complete(self) -> bool:
        """Проверить завершена ли обработка."""
        if self.status == FileStatus.FAILED:
            return True
        allowed = self.get_allowed_modules()
        return all(m in self.completed_modules for m in allowed)