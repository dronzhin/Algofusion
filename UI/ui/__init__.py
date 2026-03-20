# ui/__init__.py
from utils import setup_logger

# Инициализация логгера модуля
logger = setup_logger("ui")

__all__ = ["logger"]