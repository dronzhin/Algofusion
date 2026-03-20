# config/settings.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Приложение
    app_title: str = "File Processor Dashboard"
    app_layout: str = "wide"

    # Данные
    default_json_path: str = "data/default_template.json"
    max_logs: int = 20

    # Экспорт
    export_timeout_sec: float = 0.3
    one_c_api_url: str = ""  # Заполняется через .env

    # Кэширование
    cache_ttl_seconds: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Кэшированный доступ к настройкам"""
    return Settings()