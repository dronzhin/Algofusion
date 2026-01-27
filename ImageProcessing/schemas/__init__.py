# schemas/__init__.py
"""
Пакет схем данных API
"""
from .responses import (
    BaseResponse,
    ConvertResponse,
    RotateResponse,
    HealthCheckResponse,
    ErrorResponse
)

__all__ = [
    'BaseResponse',
    'ConvertResponse',
    'RotateResponse',
    'HealthCheckResponse',
    'ErrorResponse'
]