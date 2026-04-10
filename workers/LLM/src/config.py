# workers/LLM/src/config.py
"""
Конфигурация LLM-воркера.
"""

from dataclasses import dataclass, field
import os


@dataclass
class LLMProcessingConfig:
    """Конфигурация обработки LLM (классификация → экстракция → сохранение JSON)."""

    # === Подключение к Ollama ===
    ollama_endpoint: str = os.getenv("LLM_ENDPOINT", "http://ollama:11434")

    # 🔹 РАЗДЕЛЯЕМ модели для разных задач
    ollama_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b")  # Default для экстракции
    classifier_model: str = os.getenv("LLM_CLASSIFIER_MODEL", "qwen2.5:1.5b")  # Быстрая модель
    extractor_model: str = os.getenv("LLM_EXTRACTOR_MODEL", "qwen2.5:7b")  # Мощная модель

    ollama_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))

    # === Параметры генерации ===
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # 🔹 JSON MODE: всегда включён для гарантированного формата
    json_mode: bool = True

    # === Классификация ===
    classification_threshold: float = float(os.getenv("LLM_CLASSIFY_THRESHOLD", "0.85"))

    # 🔹 Используем значения из DocumentType enum
    allowed_doc_types: tuple[str, ...] = field(default_factory=lambda: (
        "contract", "invoice", "invoice_protocol", "waybill", "other", "unknown"
    ))

    # === Таймауты и повторные попытки ===
    classification_pending_timeout_minutes: int = int(os.getenv("LLM_PENDING_TIMEOUT_MIN", "30"))
    pending_recheck_delay_sec: int = int(os.getenv("LLM_PENDING_RECHECK_SEC", "30"))
    max_pending_requeues: int = int(os.getenv("LLM_MAX_PENDING_REQUEUES", "20"))

    # === Экстракция ===
    schemas_path: str = os.getenv("LLM_SCHEMAS_PATH", "/app/workers/LLM/schemas")
    output_format: str = os.getenv("LLM_OUTPUT_FORMAT", "json")

    # === Retry логика ===
    max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("LLM_RETRY_DELAY", "2.0"))

    # === Общие ===
    supported_input_extensions: tuple[str, ...] = field(default_factory=lambda: (
        ".txt", ".json"
    ))
    output_extension: str = ".json"
