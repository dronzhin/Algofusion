from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from shared.utils.logger import setup_logger
from .enums import DocumentType

logger = setup_logger("shared.models.file.classification")

def set_document_classification(job: "FileJob", doc_type: DocumentType, source: str = "llm", confidence: Optional[float] = None) -> None:
    now = datetime.now(timezone.utc)
    job.active_classification_source = source
    job.classification_pending = False

    if source == "llm":
        job.llm_classification_type = doc_type
        job.llm_classification_confidence = confidence
        job.llm_classification_at = now
    elif source == "user":
        job.user_classification_type = doc_type
        job.user_classification_completed_at = now
    else:
        logger.warning(f"Неизвестный источник классификации: {source}")

    job.updated_at = now
    logger.info(f"Файл {job.file_id} классифицирован как {doc_type.label} (источник: {source})")