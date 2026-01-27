# endpoints/__init__.py
"""
Пакет эндпоинтов API
"""
from .convert import convert_image_endpoint
from .rotate import rotate_image_endpoint

__all__ = ['convert_image_endpoint', 'rotate_image_endpoint']