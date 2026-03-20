# shared/config/settings.py
"""
Настройки приложения через переменные окружения.
"""

import os
from dataclasses import dataclass
from typing import Optional
from shared.utils.logger import setup_logger

logger = setup_logger("shared.config.settings")


@dataclass
class Settings:
    """Настройки приложения."""

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # Files
    shared_files_path: str = "/shared/files"
    external_monitor_path: str = "/external/incoming"

    # Monitor
    monitor_interval: int = 30

    # Workers
    worker_type: str = "preprocess"
    worker_timeout: int = 300

    # 1C Export
    export_1c_enabled: bool = False
    export_1c_endpoint: str = ""

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        """Создание настроек из переменных окружения."""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            shared_files_path=os.getenv("SHARED_FILES_PATH", "/shared/files"),
            external_monitor_path=os.getenv("EXTERNAL_MONITOR_PATH", "/external/incoming"),
            monitor_interval=int(os.getenv("MONITOR_INTERVAL", "30")),
            worker_type=os.getenv("WORKER_TYPE", "preprocess"),
            worker_timeout=int(os.getenv("WORKER_TIMEOUT", "300")),
            export_1c_enabled=os.getenv("EXPORT_1C_ENABLED", "false").lower() == "true",
            export_1c_endpoint=os.getenv("EXPORT_1C_ENDPOINT", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )

    def validate(self) -> bool:
        """Проверка валидности настроек."""
        errors = []

        if not self.redis_host:
            errors.append("REDIS_HOST не установлен")

        if self.monitor_interval < 5:
            errors.append("MONITOR_INTERVAL должен быть >= 5 секунд")

        if errors:
            for error in errors:
                logger.error(f"Ошибка валидации: {error}")
            return False

        logger.info("Настройки валидированы успешно")
        return True


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Получение настроек (синглтон)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        _settings.validate()
    return _settings