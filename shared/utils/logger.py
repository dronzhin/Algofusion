"""
Централизованная настройка логирования для всех контейнеров.
"""

import logging
import sys
from typing import Optional
import os

# Кэш логгеров
_loggers = {}


def _repair_mojibake(text: str) -> str:
    repaired = text
    for _ in range(2):
        if not any(marker in repaired for marker in ("Р", "С", "вЂ", "\xa0")):
            break
        try:
            candidate = repaired.encode("cp1251", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            break
        if not candidate or candidate == repaired:
            break
        repaired = candidate
    repaired = repaired.replace(" ониторинга", " мониторинга")
    repaired = repaired.replace(" онитора", " монитора")
    repaired = repaired.replace(" онитор ", " монитор ")
    return repaired


class SafeUnicodeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            message = record.getMessage()
            record.msg = _repair_mojibake(message)
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


def setup_logger(
        name: str,
        level: Optional[str] = None
) -> logging.Logger:
    """
    Создаёт или возвращает кэшированный логгер.

    Args:
        name: Имя логгера (обычно __name__)
        level: Уровень логирования (по умолчанию из env)

    Returns:
        Настроенный экземпляр logging.Logger
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)

    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Уровень из env или параметра
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Избегаем дублирования хендлеров
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)

        formatter = SafeUnicodeFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger
