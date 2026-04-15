#!/usr/bin/env python3
# workers/LLM/src/config.py
"""
Конфигурация LLM-воркера.
"""
from dataclasses import dataclass, field
import os
from shared.models.file.enums import DocumentType

@dataclass
class LLMProcessingConfig:
    ollama_endpoint: str = os.getenv("LLM_ENDPOINT", "http://ollama:11434")
    ollama_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    classifier_model: str = os.getenv("LLM_CLASSIFIER_MODEL", "qwen2.5:1.5b")
    extractor_model: str = os.getenv("LLM_EXTRACTOR_MODEL", "qwen2.5:7b")
    ollama_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))

    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    json_mode: bool = True

    classification_threshold: float = float(os.getenv("LLM_CLASSIFY_THRESHOLD", "0.85"))

    # 🔹 АВТОМАТИЧЕСКАЯ ПОДСТАНОВКА ТИПОВ ИЗ ENUM
    allowed_doc_types: tuple[str, ...] = field(
        default_factory=lambda: tuple(dt.value for dt in DocumentType if dt != DocumentType.UNKNOWN)
    )

    classification_pending_timeout_minutes: int = int(os.getenv("LLM_PENDING_TIMEOUT_MIN", "30"))
    pending_recheck_delay_sec: int = int(os.getenv("LLM_PENDING_RECHECK_SEC", "30"))
    max_pending_requeues: int = int(os.getenv("LLM_MAX_PENDING_REQUEUES", "20"))

    schemas_path: str = os.getenv("LLM_SCHEMAS_PATH", "/app/workers/LLM/schemas")
    output_format: str = os.getenv("LLM_OUTPUT_FORMAT", "json")
    max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("LLM_RETRY_DELAY", "2.0"))
    supported_input_extensions: tuple[str, ...] = field(default_factory=lambda: (".txt", ".json"))
    output_extension: str = ".json"