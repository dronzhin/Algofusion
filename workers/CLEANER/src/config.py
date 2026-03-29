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
    output_dpi: int = field(default_factory=lambda: int(os.getenv("CLEANER_OUTPUT_DPI", "600")))
    a4_canvas_enabled: bool = field(default_factory=lambda: os.getenv("CLEANER_A4_CANVAS_ENABLED", "true").lower() in {"1", "true", "yes", "on"})
    rotate_min_abs_angle: float = field(default_factory=lambda: float(os.getenv("CLEANER_ROTATE_MIN_ABS_ANGLE", "0.1")))
    rotate_max_abs_angle: float = field(default_factory=lambda: float(os.getenv("CLEANER_ROTATE_MAX_ABS_ANGLE", "20.0")))

    hough_canny1: int = field(default_factory=lambda: int(os.getenv("CLEANER_HOUGH_CANNY1", "50")))
    hough_canny2: int = field(default_factory=lambda: int(os.getenv("CLEANER_HOUGH_CANNY2", "150")))
    hough_threshold: int = field(default_factory=lambda: int(os.getenv("CLEANER_HOUGH_THRESHOLD", "150")))
    hough_min_line_length: int = field(default_factory=lambda: int(os.getenv("CLEANER_HOUGH_MIN_LINE_LENGTH", "200")))
    hough_max_line_gap: int = field(default_factory=lambda: int(os.getenv("CLEANER_HOUGH_MAX_LINE_GAP", "20")))
    hough_max_abs_angle: float = field(default_factory=lambda: float(os.getenv("CLEANER_HOUGH_MAX_ABS_ANGLE", "20.0")))

    text_block_size: int = field(default_factory=lambda: int(os.getenv("CLEANER_TEXT_BLOCK_SIZE", "31")))
    text_c: int = field(default_factory=lambda: int(os.getenv("CLEANER_TEXT_C", "15")))
    text_open_kernel: int = field(default_factory=lambda: int(os.getenv("CLEANER_TEXT_OPEN_KERNEL", "5")))
    text_min_contour_area: int = field(default_factory=lambda: int(os.getenv("CLEANER_TEXT_MIN_CONTOUR_AREA", "2000")))

    stage41_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE41_DIFF_MIN", "1")))
    stage41_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE41_DIFF_MAX", "11")))
    stage42_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE42_DIFF_MIN", "12")))
    stage42_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE42_DIFF_MAX", "32")))
    stage43_diff_min: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE43_DIFF_MIN", "33")))
    stage43_diff_max: int = field(default_factory=lambda: int(os.getenv("CLEANER_STAGE43_DIFF_MAX", "255")))

    bin_low_threshold: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_LOW_THRESHOLD", "96")))
    bin_mid_threshold: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_MID_THRESHOLD", "128")))
    bin_median_kernel: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_MEDIAN_KERNEL", "3")))
    bin_median_passes: int = field(default_factory=lambda: int(os.getenv("CLEANER_BIN_MEDIAN_PASSES", "3")))

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
