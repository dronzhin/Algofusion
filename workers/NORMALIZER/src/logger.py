from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        service = os.getenv("SERVICE_NAME", "normalizer-worker")
        message = f"{timestamp} | {service} | {record.levelname:8} | {record.getMessage()}"
        if hasattr(record, "context") and record.context:
            ctx = " | ".join(f"{key}={value}" for key, value in record.context.items())
            message += f" | {ctx}"
        return message


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "normalizer-worker"),
            "container_id": os.getenv("CONTAINER_ID", "unknown"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "context") and record.context:
            payload["context"] = record.context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str, level: str | None = None, format_type: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    format_type = format_type or os.getenv("LOG_FORMAT", "text").lower()
    logger.setLevel(getattr(logging, level, logging.INFO))

    formatter: logging.Formatter
    formatter = JsonFormatter() if format_type == "json" else TextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {})["context"] = {**self.extra, **kwargs.get("extra", {})}
        return msg, kwargs


def logger_with_context(logger: logging.Logger, **context: Any) -> LoggerAdapter:
    return LoggerAdapter(logger, context)
