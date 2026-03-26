# shared/utils/helpers.py
"""Shared helper utilities."""

import os
from pathlib import Path
from datetime import datetime
from typing import Union

from shared.utils.logger import setup_logger

logger = setup_logger("shared.utils.helpers")


def format_file_size(size_bytes: int) -> str:
    """Format file size into a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_datetime(dt: Union[datetime, str], format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime values for display."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    return dt.strftime(format_str)


def safe_mkdir(path: Union[str, Path], mode: int = 0o755) -> Path:
    """Create a directory and tolerate chmod failures on Windows bind mounts."""
    path = Path(path)
    try:
        old_umask = os.umask(0o022)
        try:
            path.mkdir(parents=True, exist_ok=True, mode=mode)
            try:
                os.chmod(path, mode)
            except PermissionError:
                logger.warning(f"chmod skipped for {path}: operation not permitted")
            logger.debug(f"Directory created: {path} (mode: {oct(mode)})")
            return path
        finally:
            os.umask(old_umask)
    except PermissionError as e:
        logger.error(f"Permission error while creating {path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        raise


def calculate_progress(completed: int, total: int) -> float:
    """Calculate progress as a percentage."""
    if total == 0:
        return 0.0
    return round((completed / total) * 100, 2)


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Trim long strings and append a suffix."""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix