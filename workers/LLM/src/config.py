# workers/LLM/src/config.py
"""
Конфигурация LLM-воркера.
"""

from dataclasses import dataclass, field
import os


@dataclass
class LLMProcessingConfig:
    """Конфигурация обработки LLM (классификация → экстракция → XML)."""

    # === Подключение к Ollama ===
    ollama_endpoint: str = os.getenv("LLM_ENDPOINT", "http://ollama:11434")
    ollama_model: str = os.getenv("LLM_MODEL", "mistral:7b")
    ollama_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))

    # === Параметры генерации ===
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    json_mode: bool = os.getenv("LLM_JSON_MODE", "true").lower() == "true"

    # === Классификация ===
    classification_threshold: float = float(os.getenv("LLM_CLASSIFY_THRESHOLD", "0.85"))
    allowed_doc_types: tuple[str, ...] = field(default_factory=lambda: (
        "dogovor", "schet", "tovarnaya_nakladnaya", "schet_protokol", "unknown"
    ))

    # === Таймауты и повторные попытки ===
    # Сколько минут ждать пользователя, прежде чем использовать LLM-предложение
    classification_pending_timeout_minutes: int = int(os.getenv("LLM_PENDING_TIMEOUT_MIN", "30"))
    # Базовая задержка перед повторной проверкой (сек)
    pending_recheck_delay_sec: int = int(os.getenv("LLM_PENDING_RECHECK_SEC", "30"))
    # Максимальное количество циклов ожидания (защита от вечного pending)
    max_pending_requeues: int = int(os.getenv("LLM_MAX_PENDING_REQUEUES", "20"))

    # === Экстракция ===
    schemas_path: str = os.getenv("LLM_SCHEMAS_PATH", "/app/workers/LLM/schemas")
    output_format: str = os.getenv("LLM_OUTPUT_FORMAT", "xml")

    # === Retry логика ===
    max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    retry_delay: float = float(os.getenv("LLM_RETRY_DELAY", "2.0"))

    # === Общие ===
    supported_input_extensions: tuple[str, ...] = field(default_factory=lambda: (
        ".txt", ".json"
    ))
    output_extension: str = ".xml"