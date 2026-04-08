# shared/models/file/serializer.py
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.utils.logger import setup_logger
from .enums import FileType, FileStatus, ExportStatus, DocumentType, ExportConfig, _VALID_STATUSES

logger = setup_logger("shared.models.file.serializer")


def _parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def validate_payload(payload: str) -> Tuple[bool, List[str]]:
    errors = []
    if not payload or not payload.strip():
        errors.append("Payload пустой")
        return False, errors
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        errors.append(f"Неверный JSON: {e}")
        return False, errors

    for field_name in ("file_id", "original_filename", "status"):
        if field_name not in data:
            errors.append(f"Отсутствует обязательное поле: {field_name}")

    if "file_id" in data and not isinstance(data["file_id"], str):
        errors.append("file_id должен быть строкой")
    if "original_filename" in data and not isinstance(data["original_filename"], str):
        errors.append("original_filename должен быть строкой")
    if "file_size" in data and not isinstance(data["file_size"], (int, float)):
        errors.append("file_size должен быть числом")
    if "status" in data and data["status"] not in _VALID_STATUSES:
        errors.append(f"status должен быть одним из: {_VALID_STATUSES}")

    return len(errors) == 0, errors


def to_dict(job: Any) -> Dict[str, Any]:
    return {
        "file_id": job.file_id,
        "original_filename": job.original_filename,
        "file_type": job.file_type.value,
        "file_size": job.file_size,
        "status": job.status.value,
        "current_module": job.current_module,
        "completed_modules": list(job.completed_modules),
        "ocr_engine": job.ocr_engine,
        "ocr_lang": job.ocr_lang,
        "export_to_1c": job.export_to_1c,
        "export_config": {
            "enabled": job.export_config.enabled,
            "mode": job.export_config.mode,
            "format": job.export_config.format,
            "endpoint": job.export_config.endpoint,
            "batch_size": job.export_config.batch_size
        },
        "export_status": job.export_status.value,
        "export_attempts": job.export_attempts,
        "export_error": job.export_error,
        "exported_at": job.exported_at.isoformat() if job.exported_at else None,
        "document_1c_id": job.document_1c_id,
        "config": job.config,
        "priority": job.priority,
        "callback_url": job.callback_url,
        "metadata": job.metadata,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "history": job.history,
        "llm_classification_type": job.llm_classification_type.value if job.llm_classification_type else None,
        "llm_classification_confidence": job.llm_classification_confidence,
        "llm_classification_at": job.llm_classification_at.isoformat() if job.llm_classification_at else None,
        "user_classification_type": job.user_classification_type.value if job.user_classification_type else None,
        "user_classification_requested_at": job.user_classification_requested_at.isoformat() if job.user_classification_requested_at else None,
        "user_classification_completed_at": job.user_classification_completed_at.isoformat() if job.user_classification_completed_at else None,
        "active_classification_source": job.active_classification_source,
        "classification_pending": job.classification_pending,
        "errors": job.errors
    }


def from_payload(payload: str) -> Any:
    from .job import FileJob
    try:
        data = json.loads(payload)
        logger.debug(f"Создание FileJob из payload: file_id={data.get('file_id')}")

        completed = data.get("completed_modules", [])
        if isinstance(completed, list):
            completed = set(completed)

        export_config_data = data.get("export_config", {})
        export_config = ExportConfig(**export_config_data) if export_config_data else ExportConfig()

        return FileJob(
            file_id=data.get("file_id", "unknown"),
            original_filename=data.get("original_filename", "unknown"),
            file_type=FileType(data.get("file_type", "unknown")),
            file_size=data.get("file_size", 0),
            status=FileStatus(data.get("status", "uploaded")),
            current_module=data.get("current_module"),
            completed_modules=completed,
            ocr_engine=data.get("ocr_engine", "tesseract"),
            ocr_lang=data.get("ocr_lang", "rus+eng"),
            export_to_1c=data.get("export_to_1c", False),
            export_config=export_config,
            export_status=ExportStatus(data.get("export_status", "pending")),
            export_attempts=data.get("export_attempts", 0),
            export_error=data.get("export_error"),
            exported_at=_parse_datetime(data["exported_at"]) if data.get("exported_at") else None,
            document_1c_id=data.get("document_1c_id"),
            config=data.get("config", {}),
            priority=data.get("priority", 0),
            callback_url=data.get("callback_url"),
            metadata=data.get("metadata", {}),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            history=data.get("history", []),
            llm_classification_type=DocumentType.safe_parse(data.get("llm_classification_type")),
            llm_classification_confidence=data.get("llm_classification_confidence"),
            llm_classification_at=_parse_datetime(data["llm_classification_at"]) if data.get("llm_classification_at") else None,
            user_classification_type=DocumentType.safe_parse(data.get("user_classification_type")),
            user_classification_requested_at=_parse_datetime(data["user_classification_requested_at"]) if data.get("user_classification_requested_at") else None,
            user_classification_completed_at=_parse_datetime(data["user_classification_completed_at"]) if data.get("user_classification_completed_at") else None,
            active_classification_source=data.get("active_classification_source"),
            classification_pending=data.get("classification_pending", False),
            errors=data.get("errors", [])
        )
    except Exception as e:
        logger.error(f"Ошибка парсинга payload: {e}", exc_info=True)
        raise


def from_payload_safe(payload: str) -> Tuple[Optional[Any], Optional[str]]:
    is_valid, errors = validate_payload(payload)
    if not is_valid:
        return None, "; ".join(errors)
    try:
        return from_payload(payload), None
    except Exception as e:
        return None, f"Ошибка парсинга: {e}"