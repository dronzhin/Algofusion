# core/__init__.py
"""Сервисы."""
from core.services.redis_client import get_redis_client, RedisClient
from core.services.file_service import FileService

__all__ = ["get_redis_client", "RedisClient", "FileService"]