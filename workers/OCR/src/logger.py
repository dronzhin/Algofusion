# workers/ocr/src/logger.py
"""Простое логирование для OCR-воркера."""

import logging
import sys
import json
import os
from datetime import datetime
from typing import Any, Dict


class SimpleFormatter(logging.Formatter):
    """Текстовый форматтер с эмодзи."""

    EMOJIS = {
        "DEBUG": "🐛",
        "INFO": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🔥"
    }

    def format(self, record: logging.LogRecord) -> str:
        emoji = self.EMOJIS.get(record.levelname, "ℹ️")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        service = os.getenv("SERVICE_NAME", "ocr-worker")

        msg = f"{emoji} {timestamp} | {service} | {record.levelname:8} | {record.getMessage()}"

        if hasattr(record, "context") and record.context:
            ctx = " | ".join(f"{k}={v}" for k, v in record.context.items())
            msg += f" | {ctx}"

        return msg


class JSONFormatter(logging.Formatter):
    """JSON форматтер для ELK/Cloud."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "ocr-worker"),
            "container_id": os.getenv("CONTAINER_ID", "unknown"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "context") and record.context:
            log_data["context"] = record.context

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def get_logger(name: str, level: str = None, format_type: str = None) -> logging.Logger:
    """Создаёт или получает логгер."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    format_type = format_type or os.getenv("LOG_FORMAT", "text").lower()

    logger.setLevel(getattr(logging, level, logging.INFO))

    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = SimpleFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False

    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """Адаптер для добавления контекста."""

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {})["context"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


def logger_with_context(logger: logging.Logger, **context: Any) -> LoggerAdapter:
    """Создаёт адаптер логгера с контекстом."""
    return LoggerAdapter(logger, context)