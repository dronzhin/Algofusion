# utils/logger.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_app_logger(
        name: str = "app",
        level: str = "INFO",
        log_file: Optional[str] = None,
        max_bytes: int = 5 * 1024 * 1024,  # 5 MB
        backup_count: int = 3  # хранить до 3 архивных файлов
) -> logging.Logger:
    """
    Настраивает изолированный логгер с ротацией файлов.

    Args:
        name: Имя логгера
        level: Уровень логирования
        log_file: Путь к основному файлу лога
        max_bytes: Максимальный размер одного файла (в байтах)
        backup_count: Сколько архивных файлов хранить
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Избегаем дублирования хендлеров (важно для Streamlit!)
    if logger.handlers:
        logger.handlers.clear()

    # Форматтер
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)-20s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Файл с ротацией
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,  # например, 5 MB
            backupCount=backup_count  # будет: app.log, app.log.1, app.log.2, app.log.3
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger