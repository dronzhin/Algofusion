# schemas/responses.py
"""
Схемы ответов API
"""
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """Базовая схема ответа"""
    success: bool
    message: str = None


class ConvertResponse(BaseResponse):
    """Схема ответа для конвертации"""
    images_base64: list
    count: int
    details: dict = None


class RotateResponse(BaseResponse):
    """Схема ответа для поворота"""
    rotated_image_base64: str = None
    rotation_angle: float
    line_info: dict = None
    debug_info: dict = None
    error: str = None


class HealthCheckResponse(BaseModel):
    """Схема ответа для проверки состояния"""
    status: str
    timestamp: float
    version: str
    uptime: float = None


class ErrorResponse(BaseModel):
    """Схема ошибочного ответа"""
    success: bool = False
    error: str
    error_type: str = None
    timestamp: float
    details: dict = None