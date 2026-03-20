# utils/logger.py
"""
Централизованная настройка логирования для UI-модуля
"""
import logging
import sys
from pathlib import Path
from typing import Optional

# Кэш логгеров для предотвращения дублирования хендлеров
_loggers = {}


def setup_logger(
        name: str,
        level: int = logging.INFO,
        log_to_file: bool = False,
        log_dir: Optional[Path] = None
) -> logging.Logger:
    """
    Создаёт или возвращает кэшированный логгер с настройкой хендлеров.

    Args:
        name: Имя логгера (обычно __name__)
        level: Уровень логирования
        log_to_file: Писать ли в файл
        log_dir: Директория для логов

    Returns:
        Настроенный экземпляр logging.Logger
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Избегаем дублирования хендлеров при перезагрузке Streamlit
    if not logger.handlers:
        # Консольный хендлер
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # Файловый хендлер (опционально)
        if log_to_file:
            log_directory = log_dir or Path("logs")
            log_directory.mkdir(exist_ok=True)
            file_handler = logging.FileHandler(
                log_directory / f"{name.replace('.', '_')}.log",
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(console_formatter)
            logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger