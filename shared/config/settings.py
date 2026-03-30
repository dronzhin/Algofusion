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
    monitor_interval: int = 5

    # Workers
    worker_type: str = "preprocess"
    worker_timeout: int = 300

    # 1C Export
    export_1c_enabled: bool = False
    export_1c_endpoint: str = ""

    # Logging
    log_level: str = "INFO"

    # UI Auto-refresh defaults
    ui_auto_refresh_enabled: bool = True
    ui_auto_refresh_interval_sec: int = 5
    ui_auto_refresh_min_sec: int = 5
    ui_auto_refresh_max_sec: int = 60
    app_version: str = "0.1.0"
    environment: str = "development"

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
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            ui_auto_refresh_enabled=os.getenv("UI_AUTO_REFRESH_ENABLED", "true").lower() == "true",
            ui_auto_refresh_interval_sec=int(os.getenv("UI_AUTO_REFRESH_INTERVAL_SEC", "5")),
            ui_auto_refresh_min_sec=int(os.getenv("UI_AUTO_REFRESH_MIN_SEC", "5")),
            ui_auto_refresh_max_sec=int(os.getenv("UI_AUTO_REFRESH_MAX_SEC", "60")),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            environment=os.getenv("ENVIRONMENT", "development")
        )

    def validate(self) -> bool:
        """Проверка валидности настроек."""
        errors = []

        # === Инфраструктура (критично для всех модулей) ===
        if not self.redis_host:
            errors.append("REDIS_HOST не установлен")
        if not self.redis_port:
            errors.append("REDIS_PORT не установлен")
        if not self.shared_files_path:
            errors.append("SHARED_FILES_PATH не установлен")

        # === Монитор (специфика) ===
        if self.monitor_interval < 5:
            errors.append("MONITOR_INTERVAL должен быть >= 5 секунд")

        # === UI (специфика) ===
        if not (5 <= self.ui_auto_refresh_min_sec <= self.ui_auto_refresh_max_sec <= 300):
            errors.append("UI_AUTO_REFRESH: MIN должен быть >=5, MAX <=300, MIN <= MAX")
        if not (self.ui_auto_refresh_min_sec <= self.ui_auto_refresh_interval_sec <= self.ui_auto_refresh_max_sec):
            errors.append("UI_AUTO_REFRESH_INTERVAL_SEC вне диапазона [MIN, MAX]")

        if errors:
            for error in errors:
                logger.error(f"❌ Ошибка валидации настроек: {error}")
            logger.error("💡 Проверьте переменные окружения в docker-compose.yml или .env")
            return False

        logger.info("✅ Настройки валидированы успешно")
        return True


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Получение настроек (синглтон)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        _settings.validate()
    return _settings