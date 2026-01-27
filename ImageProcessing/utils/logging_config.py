# logging_config.py
"""
Модуль настройки логирования для приложения
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Кастомный форматтер с цветами для консоли"""

    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'  # Reset
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname_colored = f"{log_color}{record.levelname}{self.COLORS['RESET']}"

        # Добавляем информацию о времени и модуле
        record.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        return super().format(record)


def setup_logging(log_level: str = "INFO",
                  log_file: str = None,
                  enable_console: bool = True,
                  enable_file: bool = True) -> logging.Logger:
    """
    Настройка логирования для приложения

    Args:
        log_level: Уровень логирования
        log_file: Путь к файлу логов
        enable_console: Включить логирование в консоль
        enable_file: Включить логирование в файл
    """
    # Создаем корневой логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Очищаем существующие хендлеры
    logger.handlers.clear()

    # Формат сообщений
    console_format = ColoredFormatter(
        '%(levelname_colored)s | %(asctime)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    if enable_file and log_file:
        # Создаем директорию для логов, если не существует
        log_path = Path(log_file).parent
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер для конкретного модуля

    Args:
        name: Имя логгера (обычно __name__)
    """
    return logging.getLogger(name)


# Глобальный экземпляр для использования в приложении
default_logger = setup_logging()