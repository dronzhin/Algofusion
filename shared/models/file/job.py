#!/usr/bin/env python3
# shared/models/file/job.py
"""
Модель задания на обработку файла.
Содержит метаданные, состояние, маршрутизацию и константы очередей/каналов.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, ClassVar
import json

from shared.utils.logger import setup_logger
from .enums import FileType, FileStatus, ExportStatus, ExportConfig
from .serializer import to_dict as _to_dict, from_payload as _from_payload, from_payload_safe as _from_payload_safe, \
    validate_payload as _validate_payload
from .routing import (
    get_queue_for_module as _get_queue_for_module, get_all_queues as _get_all_queues,
    is_valid_queue_module as _is_valid_queue_module, detect_file_type as _detect_file_type,
    get_allowed_modules as _get_allowed_modules, get_base_path as _get_base_path,
    get_original_path as _get_original_path, get_module_input_path as _get_module_input_path,
    get_module_output_path as _get_module_output_path, get_export_path as _get_export_path,
    get_archive_path as _get_archive_path
)
from .classification import set_document_classification as _set_classification
from .events import (
    build_uploaded_event as _build_uploaded_event, build_status_changed_event as _build_status_changed_event,
    build_processing_error_event as _build_processing_error_event, build_exported_event as _build_exported_event,
    publish_event as _publish_event, EVENT_CHANNEL, EVENT_VERSION
)

logger = setup_logger("shared.models.file.job")


@dataclass
class FileJob:
    # --- Основные поля ---
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

    # --- Классификация (используем str для совместимости с config) ---
    llm_classification_type: Optional[str] = None
    llm_classification_confidence: Optional[float] = None
    llm_classification_at: Optional[datetime] = None
    user_classification_type: Optional[str] = None
    user_classification_requested_at: Optional[datetime] = None
    user_classification_completed_at: Optional[datetime] = None
    active_classification_source: Optional[str] = None
    classification_pending: bool = False

    # === КОНСТАНТЫ ОЧЕРЕДЕЙ И КАНАЛОВ (Единый источник) ===
    QUEUE_PREPROCESS: ClassVar[str] = "files:preprocess"
    QUEUE_OCR: ClassVar[str] = "files:ocr"
    QUEUE_LLM: ClassVar[str] = "files:llm"
    QUEUE_EXPORT: ClassVar[str] = "files:export"

    # Pub/Sub каналы для уведомлений UI (не сохраняются в Redis, fire-and-forget)
    CHANNEL_UI_LLM_REQUESTS: ClassVar[str] = "ui:llm_requests"
    CHANNEL_UI_EXPORT_READY: ClassVar[str] = "ui:export_ready"
    CHANNEL_UI_ERRORS: ClassVar[str] = "ui:errors"

    # Реестры для итерации/мониторинга
    QUEUES: ClassVar[Dict[str, str]] = {
        "preprocess": QUEUE_PREPROCESS, "ocr": QUEUE_OCR,
        "llm": QUEUE_LLM, "export": QUEUE_EXPORT
    }
    UI_CHANNELS: ClassVar[Dict[str, str]] = {
        "llm_requests": CHANNEL_UI_LLM_REQUESTS,
        "export_ready": CHANNEL_UI_EXPORT_READY,
        "errors": CHANNEL_UI_ERRORS,
    }

    EVENT_CHANNEL: ClassVar[str] = EVENT_CHANNEL
    EVENT_VERSION: ClassVar[str] = EVENT_VERSION

    # === Методы-обёртки ===
    @classmethod
    def validate_payload(cls, payload: str): return _validate_payload(payload)

    @classmethod
    def from_payload_safe(cls, payload: str): return _from_payload_safe(payload)

    @classmethod
    def from_payload(cls, payload: str) -> "FileJob": return _from_payload(payload)

    def to_dict(self) -> Dict[str, Any]: return _to_dict(self)

    def to_payload(self) -> str: return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def get_queue_for_module(cls, module: str) -> Optional[str]: return _get_queue_for_module(module)

    @classmethod
    def get_all_queues(cls) -> Dict[str, str]: return _get_all_queues()

    @classmethod
    def is_valid_queue_module(cls, module: str) -> bool: return _is_valid_queue_module(module)

    @classmethod
    def detect_file_type(cls, filename: str) -> FileType: return _detect_file_type(filename)

    def get_allowed_modules(self) -> List[str]: return _get_allowed_modules(self.file_type)

    def get_base_path(self, base_dir: str = "/shared/files") -> Any: return _get_base_path(self.file_id, base_dir)

    def get_original_path(self, base_dir: str = "/shared/files") -> Any: return _get_original_path(self.file_id,
                                                                                                   self.original_filename,
                                                                                                   base_dir)

    def get_module_input_path(self, module: str, base_dir: str = "/shared/files") -> Any: return _get_module_input_path(
        self, module, base_dir)

    def get_module_output_path(self, module: str,
                               base_dir: str = "/shared/files") -> Any: return _get_module_output_path(self, module,
                                                                                                       base_dir)

    def get_export_path(self, base_dir: str = "/shared/files") -> Any: return _get_export_path(self, base_dir)

    def get_archive_path(self, base_dir: str = "/shared/files") -> Any: return _get_archive_path(self, base_dir)

    def complete_module(self, module: str):
        self.completed_modules.add(module)
        self.current_module = None
        self.updated_at = datetime.now(timezone.utc)
        logger.debug(f"Модуль {module} завершён для файла {self.file_id}")

    def add_to_history(self, action: str, module: str, success: bool, error: str = None, duration: float = None):
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
        if self.status == FileStatus.FAILED:
            return True
        return all(m in self.completed_modules for m in self.get_allowed_modules())

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def increment_retry(self):
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)

    def set_document_classification(self, doc_type: str, source: str = "llm", confidence: Optional[float] = None):
        _set_classification(self, doc_type, source, confidence)

    @classmethod
    def build_uploaded_event(cls, *a, **k): return _build_uploaded_event(*a, **k)

    @classmethod
    def build_status_changed_event(cls, *a, **k): return _build_status_changed_event(*a, **k)

    @classmethod
    def build_processing_error_event(cls, *a, **k): return _build_processing_error_event(*a, **k)

    @classmethod
    def build_exported_event(cls, *a, **k): return _build_exported_event(*a, **k)

    @classmethod
    def publish_event(cls, redis_client, event: Dict[str, Any]) -> int:
        return _publish_event(redis_client, event)