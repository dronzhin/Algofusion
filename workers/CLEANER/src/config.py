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
    assumed_input_dpi: int = field(default_factory=lambda: int(os.getenv("CLEANER_ASSUMED_INPUT_DPI", "300")))
    output_dpi: int = field(default_factory=lambda: int(os.getenv("CLEANER_OUTPUT_DPI", "600")))
    a4_canvas_enabled: bool = field(default_factory=lambda: os.getenv("CLEANER_A4_CANVAS_ENABLED", "true").lower() in {"1", "true", "yes", "on"})
    rotate_min_abs_angle: float = field(default_factory=lambda: float(os.getenv("CLEANER_ROTATE_MIN_ABS_ANGLE", "0.0")))

    stage41_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE41_DIFF_MIN", "1")))
    stage41_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE41_DIFF_MAX", "11")))
    stage42_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE42_DIFF_MIN", "12")))
    stage42_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE42_DIFF_MAX", "32")))
    stage43_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE43_DIFF_MIN", "33")))
    stage43_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE43_DIFF_MAX", "255")))

    background_threshold: int = field(default_factory=lambda: int(os.getenv("CLEANER_BACKGROUND_THRESHOLD", "128")))
    background_fill_value: int = field(default_factory=lambda: int(os.getenv("CLEANER_BACKGROUND_FILL_VALUE", "255")))
    binary_threshold: int = field(default_factory=lambda: int(os.getenv("CLEANER_BINARY_THRESHOLD", "128")))
    binary_foreground_value: int = field(default_factory=lambda: int(os.getenv("CLEANER_BINARY_FOREGROUND_VALUE", "1")))
    binary_background_value: int = field(default_factory=lambda: int(os.getenv("CLEANER_BINARY_BACKGROUND_VALUE", "255")))
    bin_median_kernel: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_MEDIAN_KERNEL", "3")))
    bin_median_passes: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_MEDIAN_PASSES", "5")))

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
