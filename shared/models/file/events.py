# shared/models/file/events.py
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

EVENT_CHANNEL = "files:events"
EVENT_VERSION = "1.0"

def build_uploaded_event(file_id: str, filename: str, file_type: str, file_size: int, **extra) -> Dict[str, Any]:
    return {"type": "file_uploaded", "version": EVENT_VERSION, "file_id": file_id,
            "filename": filename, "file_type": file_type, "file_size": file_size,
            "timestamp": datetime.now(timezone.utc).isoformat(), **extra}

def build_status_changed_event(file_id: str, status: str, current_module: Optional[str] = None,
                               completed_modules: Optional[List[str]] = None, error: Optional[str] = None,
                               filename: Optional[str] = None, page_count: Optional[int] = None, **extra) -> Dict[str, Any]:
    event = {"type": "file_status_changed", "version": EVENT_VERSION, "file_id": file_id,
             "status": status, "timestamp": datetime.now(timezone.utc).isoformat()}
    if current_module is not None: event["current_module"] = current_module
    if completed_modules is not None: event["completed_modules"] = completed_modules
    if error is not None: event["error"] = error
    if filename is not None: event["filename"] = filename
    if page_count is not None: event["page_count"] = page_count
    event.update(extra)
    return event

def build_processing_error_event(file_id: str, error: str, module: Optional[str] = None,
                                 exception_type: Optional[str] = None, **extra) -> Dict[str, Any]:
    event = {"type": "processing_error", "version": EVENT_VERSION, "file_id": file_id,
             "error": error, "timestamp": datetime.now(timezone.utc).isoformat()}
    if module is not None: event["module"] = module
    if exception_type is not None: event["exception_type"] = exception_type
    event.update(extra)
    return event

def build_exported_event(file_id: str, export_status: str, document_1c_id: Optional[str] = None,
                         error: Optional[str] = None, **extra) -> Dict[str, Any]:
    event = {"type": "file_exported", "version": EVENT_VERSION, "file_id": file_id,
             "export_status": export_status, "timestamp": datetime.now(timezone.utc).isoformat()}
    if document_1c_id is not None: event["document_1c_id"] = document_1c_id
    if error is not None: event["error"] = error
    event.update(extra)
    return event

def publish_event(redis_client: Any, event: Dict[str, Any]) -> int:
    return redis_client.publish_structured_event(
        channel=EVENT_CHANNEL, event_type=event["type"], file_id=event.get("file_id"),
        version=event.get("version", EVENT_VERSION),
        **{k: v for k, v in event.items() if k not in ["type", "version", "timestamp", "file_id"]}
    )