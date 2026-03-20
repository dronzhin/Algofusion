# workers/ocr/src/config.py
"""Конфигурация OCR-воркера."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """Конфигурация из environment variables."""

    # Redis
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0"))
    redis_queue: str = field(default_factory=lambda: os.getenv("OCR_QUEUE", "files:ocr"))
    redis_timeout: int = field(default_factory=lambda: int(os.getenv("BLPOP_TIMEOUT", "5")))

    # Пути
    shared_files_dir: Path = field(default_factory=lambda: Path(os.getenv("SHARED_FILES_DIR", "/shared/files")))

    # OCR по умолчанию
    default_ocr_engine: str = field(default_factory=lambda: os.getenv("DEFAULT_OCR_ENGINE", "tesseract"))
    default_ocr_lang: str = field(default_factory=lambda: os.getenv("DEFAULT_OCR_LANG", "rus+eng"))
    default_oem: int = field(default_factory=lambda: int(os.getenv("DEFAULT_OCR_OEM", "1")))
    default_psm: int = field(default_factory=lambda: int(os.getenv("DEFAULT_OCR_PSM", "1")))

    # Worker
    container_id: str = field(default_factory=lambda: os.getenv("CONTAINER_ID", "ocr-worker"))
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "ocr-worker"))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))

    # Логирование
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "text"))

    @classmethod
    def validate(cls) -> bool:
        """Проверка обязательных переменных."""
        if not os.getenv("REDIS_URL"):
            raise ValueError("Требуется переменная REDIS_URL")
        return True


config = Config()