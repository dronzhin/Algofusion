from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0"))
    redis_queue: str = field(default_factory=lambda: os.getenv("PARSER_QUEUE", "files:parser"))
    next_queue: str = field(default_factory=lambda: os.getenv("NEXT_QUEUE", "files:normalizer"))
    redis_timeout: int = field(default_factory=lambda: int(os.getenv("BLPOP_TIMEOUT", "5")))

    shared_files_dir: Path = field(default_factory=lambda: Path(os.getenv("SHARED_FILES_DIR", "/shared/files")))

    container_id: str = field(default_factory=lambda: os.getenv("CONTAINER_ID", "parser-worker"))
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "parser-worker"))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "text"))

    @classmethod
    def validate(cls) -> bool:
        if not os.getenv("REDIS_URL"):
            raise ValueError("REDIS_URL is required")
        return True


config = Config()
