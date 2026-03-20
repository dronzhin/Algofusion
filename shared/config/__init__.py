# shared/config/__init__.py
"""Конфигурация приложения."""
from shared.config.settings import get_settings, Settings

__all__ = ["get_settings", "Settings"]