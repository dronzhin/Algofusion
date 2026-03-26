from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json


class FileType(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


@dataclass
class FileJob:
    file_id: str
    original_filename: str
    file_type: FileType = FileType.UNKNOWN
    file_size: int = 0
    status: FileStatus = FileStatus.UPLOADED
    current_module: Optional[str] = None
    completed_modules: Set[str] = field(default_factory=set)
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_payload(cls, payload: str) -> "FileJob":
        data = json.loads(payload)
        completed = data.get("completed_modules", [])
        if isinstance(completed, list):
            completed = set(completed)
        return cls(
            file_id=data.get("file_id", "unknown"),
            original_filename=data.get("original_filename", "unknown"),
            file_type=FileType(data.get("file_type", "unknown")),
            file_size=data.get("file_size", 0),
            status=FileStatus(data.get("status", "uploaded")),
            current_module=data.get("current_module"),
            completed_modules=completed,
            config=data.get("config", {}),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            history=data.get("history", []),
            errors=data.get("errors", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "status": self.status.value,
            "current_module": self.current_module,
            "completed_modules": list(self.completed_modules),
            "config": self.config,
            "priority": self.priority,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "history": self.history,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_payload(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def get_storage_dir_name(self) -> str:
        return Path(self.original_filename).stem

    def get_base_path(self, base_dir: str = "/shared/files") -> Path:
        base_dir_path = Path(base_dir)
        preferred = base_dir_path / self.get_storage_dir_name()
        legacy = base_dir_path / self.file_id
        if legacy.exists() and not preferred.exists():
            return legacy
        return preferred

    def get_original_path(self, base_dir: str = "/shared/files") -> Path:
        return self.get_base_path(base_dir) / "original" / self.original_filename

    def get_module_dir(self, module: str, base_dir: str = "/shared/files") -> Path:
        path = self.get_base_path(base_dir) / module
        path.mkdir(parents=True, exist_ok=True)
        return path

    def complete_module(self, module: str) -> None:
        self.completed_modules.add(module)
        self.current_module = None
        self.updated_at = datetime.utcnow()

    def fail_module(self, module: str, error: str) -> None:
        self.status = FileStatus.FAILED
        self.current_module = module
        self.errors.append(error)
        self.updated_at = datetime.utcnow()

    def add_to_history(
        self,
        action: str,
        module: str,
        success: bool,
        error: str | None = None,
        duration: float | None = None,
    ) -> None:
        self.history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "module": module,
                "action": action,
                "success": success,
                "error": error,
                "duration_seconds": duration,
            }
        )
        self.updated_at = datetime.utcnow()
