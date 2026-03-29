from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0"))
    redis_queue: str = field(default_factory=lambda: os.getenv("CLEANER_QUEUE", "files:cleaner"))
    next_queue: str = field(default_factory=lambda: os.getenv("NEXT_QUEUE", "files:layout"))
    redis_timeout: int = field(default_factory=lambda: int(os.getenv("BLPOP_TIMEOUT", "5")))

    shared_files_dir: Path = field(default_factory=lambda: Path(os.getenv("SHARED_FILES_DIR", "/shared/files")))

    default_dpi: int = field(default_factory=lambda: int(os.getenv("CLEANER_DPI", "600")))
    output_dpi: int = field(default_factory=lambda: int(os.getenv("CLEANER_OUTPUT_DPI", "200")))
    container_id: str = field(default_factory=lambda: os.getenv("CONTAINER_ID", "cleaner-worker"))
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "cleaner-worker"))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "text"))

    @classmethod
    def validate(cls) -> bool:
        if not os.getenv("REDIS_URL"):
            raise ValueError("REDIS_URL is required")
        return True


config = Config()
