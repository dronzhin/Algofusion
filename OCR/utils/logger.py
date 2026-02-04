# utils/logger.py

"""
Настройки логирования для OCR сервера.
Создаёт папку logs/ и ротирует логи (максимум 3 файла по 3 МБ).
"""

import logging
import logging.handlers
import os
from pathlib import Path
import sys


def setup_logger(name: str = "ocr_server", log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    """
    Настройка логгера с ротацией файлов.

    Args:
        name: имя логгера
        log_dir: директория для сохранения логов
        level: уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Настроенный логгер
    """

    # Создаём директорию для логов, если её нет
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Создаём логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Очищаем существующие хэндлеры (чтобы избежать дублирования)
    if logger.handlers:
        logger.handlers.clear()

    # Формат сообщений
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Хэндлер для файла с ротацией (максимум 3 файла по 3 МБ)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "ocr_server.log",
        maxBytes=3 * 1024 * 1024,  # 3 МБ
        backupCount=2,              # 2 резервных файла + текущий = 3 файла всего
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Хэндлер для консоли (цветной вывод)
    class ColoredFormatter(logging.Formatter):
        """Цветной форматтер для консоли"""
        COLORS = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
            'RESET': '\033[0m'      # Reset
        }

        def format(self, record):
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            return super().format(record)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-18s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # Добавляем хэндлеры к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Логируем информацию о настройке
    logger.info("=" * 70)
    logger.info(f"Логирование настроено | Уровень: {level} | Директория: {log_path.absolute()}")
    logger.info(f"Ротация: максимум 3 файла по 3 МБ каждый")
    logger.info("=" * 70)

    return logger


def get_logger(name: str = "ocr_server") -> logging.Logger:
    """
    Получение уже настроенного логгера.
    Если логгер ещё не настроен, создаёт новый с настройками по умолчанию.

    Args:
        name: имя логгера

    Returns:
        Логгер
    """
    logger = logging.getLogger(name)

    # Если логгер ещё не настроен (нет хэндлеров)
    if not logger.handlers:
        return setup_logger(name)

    return logger


# Создаём глобальный логгер для импорта
logger = get_logger()


if __name__ == "__main__":
    # Тестовый запуск для проверки настроек
    test_logger = setup_logger(level="DEBUG")

    test_logger.debug("Это сообщение уровня DEBUG")
    test_logger.info("Это сообщение уровня INFO")
    test_logger.warning("Это сообщение уровня WARNING")
    test_logger.error("Это сообщение уровня ERROR")
    test_logger.critical("Это сообщение уровня CRITICAL")

    # Проверка ротации
    for i in range(100):
        test_logger.info(f"Тестовое сообщение #{i}")

    print(f"\n✅ Логи сохранены в: {Path('logs').absolute()}")
    print(f"   Файлы: {os.listdir('logs')}")