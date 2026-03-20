"""
Централизованная настройка логирования для всех контейнеров.
"""

import logging
import sys
from typing import Optional
import os

# Кэш логгеров
_loggers = {}


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

    # Уровень из env или параметра
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Избегаем дублирования хендлеров
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger