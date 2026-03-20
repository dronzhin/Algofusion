# utils/__init__.py

from utils.logger import setup_logger

# Инициализация логгера модуля
logger = setup_logger("ui")

__all__ = ["logger"]