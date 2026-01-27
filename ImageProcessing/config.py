# config.py
"""
Конфигурация приложения
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
import os


class Settings(BaseSettings):
    """Класс конфигурации приложения"""

    app_name: str = "Image Processing API"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=1)

    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(default=None)

    max_file_size: int = Field(default=10 * 1024 * 1024, ge=1024, le=50*1024*1024)
    allowed_extensions: set = {"jpg", "jpeg", "png", "bmp", "gif", "webp", "pdf"}
    allowed_content_types: set = {
        "image/jpeg", "image/jpg", "image/png", "image/bmp",
        "image/gif", "image/x-png", "image/pjpeg",
        "image/x-jpg", "image/webp", "application/pdf"
    }

    default_threshold: int = Field(default=128, ge=0, le=255)
    default_min_line_length: int = Field(default=50, ge=10, le=500)
    default_max_line_gap: int = Field(default=20, ge=1, le=100)

    upload_dir: Path = Path("uploads")
    temp_dir: Path = Path("temp")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )


# Глобальный экземпляр настроек
settings = Settings()