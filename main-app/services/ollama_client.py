# services/ollama_client.py
"""
Универсальный клиент для работы с любыми моделями через Ollama
"""

import base64
import io
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from PIL import Image
import requests

from config import Config
from utils import APIError, ImageProcessingError
from .models import ModelBase, ModelInput, ModelOutput, ModelType
from .models.factory import ModelFactory

logger = logging.getLogger(__name__)


class OllamaClient:
    """Универсальный клиент для работы с моделями через Ollama"""

    def __init__(self):
        ollama_config = Config.get_ollama_config()
        self.base_url = ollama_config["base_url"].rstrip("/")
        self.timeout = ollama_config["timeout"]
        self.session = requests.Session()

        # Кэш созданных моделей
        self._model_cache: Dict[str, ModelBase] = {}

        # Кэш доступных моделей на сервере
        self._server_models_cache: Optional[List[str]] = None
        self._server_models_cache_time: float = 0
        self._cache_ttl: int = 300  # 5 минут

    def health_check(self) -> bool:
        """Проверка доступности Ollama сервера"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama недоступен: {e}")
            return False

    def get_server_models(self, force_refresh: bool = False) -> List[str]:
        """
        Получение списка моделей, доступных на сервере Ollama

        Args:
            force_refresh: принудительное обновление кэша

        Returns:
            Список имён моделей
        """
        current_time = time.time()

        # Использование кэша
        if (not force_refresh and
                self._server_models_cache is not None and
                current_time - self._server_models_cache_time < self._cache_ttl):
            return self._server_models_cache

        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            response.raise_for_status()

            models_data = response.json().get("models", [])
            self._server_models_cache = [m["name"] for m in models_data]
            self._server_models_cache_time = current_time

            return self._server_models_cache

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей с сервера: {e}")
            return []

    def get_available_models(
            self,
            model_type: Optional[str] = None,
            include_server_info: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Получение списка доступных моделей с метаданными

        Args:
            model_type: фильтр по типу ("text", "vision", "ocr", "all")
            include_server_info: включать информацию о наличии на сервере

        Returns:
            Список словарей с информацией о моделях
        """
        # Получение зарегистрированных моделей
        if model_type == "all" or model_type is None:
            models_info = ModelFactory.get_models_by_category()
        else:
            # Фильтрация по типу
            type_enum = getattr(ModelType, model_type.upper(), None)
            models_info = ModelFactory.get_available_models(
                model_type=type_enum
            ) if type_enum else {}

        result = []

        # Получение моделей на сервере
        server_models = self.get_server_models() if include_server_info else []

        # Обработка категоризированного формата
        if isinstance(models_info, dict):
            for category, models in models_info.items():
                if isinstance(models, list):
                    for model in models:
                        model_entry = {
                            "category": category,
                            "available_on_server": model.get("model_name", "") in server_models,
                            **model
                        }
                        result.append(model_entry)
                elif isinstance(models, dict):
                    # Старый формат - плоский словарь
                    for model_name, metadata in models.items():
                        model_entry = {
                            "name": model_name,
                            "category": category,
                            **metadata,
                            "available_on_server": model_name in server_models
                        }
                        result.append(model_entry)

        return result

    def _get_model_instance(self, model_name: str) -> ModelBase:
        """
        Получение экземпляра модели из кэша или создание нового

        Args:
            model_name: имя модели

        Returns:
            Экземпляр модели

        Raises:
            ValueError: если модель не найдена
        """
        # Проверка кэша
        if model_name in self._model_cache:
            return self._model_cache[model_name]

        # Создание новой модели
        model_instance = ModelFactory.create_model(
            model_name,
            self.base_url,
            self.timeout
        )

        if not model_instance:
            available_models = list(ModelFactory.get_available_models().keys())
            raise ValueError(
                f"Модель '{model_name}' не найдена. "
                f"Доступные модели: {', '.join(available_models) if available_models else 'нет зарегистрированных моделей'}"
            )

        # Кэширование
        self._model_cache[model_name] = model_instance
        return model_instance

    def _prepare_image_base64(
            self,
            file_data: bytes,
            filename: str,
            max_size: int = 10 * 1024 * 1024  # 10MB
    ) -> str:
        """
        Подготовка изображения в base64 формат

        Args:
            file_data: байты файла
            filename: имя файла
            max_size: максимальный размер в байтах

        Returns:
            Изображение в base64
        """
        try:
            file_ext = Path(filename).suffix.lower()

            # Обработка изображений
            if file_ext in Config.SUPPORTED_IMAGE_EXTENSIONS:
                # Проверка и уменьшение размера при необходимости
                if len(file_data) > max_size:
                    logger.info(f"Изображение {filename} превышает {max_size} байт, уменьшаем...")
                    img = Image.open(io.BytesIO(file_data))
                    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img_format = img.format or 'PNG'
                    img.save(buffer, format=img_format, quality=85)
                    file_data = buffer.getvalue()

                return base64.b64encode(file_data).decode('utf-8')

            # Обработка PDF (берём первую страницу)
            elif file_ext == '.pdf':
                try:
                    from pdf2image import convert_from_bytes
                    logger.info(f"Конвертация первой страницы PDF: {filename}")
                    images = convert_from_bytes(
                        file_data,
                        dpi=Config.DEFAULT_DPI,
                        first_page=1,
                        last_page=1
                    )
                    if not images:
                        raise ImageProcessingError("PDF не содержит страниц")

                    buffer = io.BytesIO()
                    images[0].save(buffer, format='PNG', quality=85)
                    return base64.b64encode(buffer.getvalue()).decode('utf-8')

                except ImportError:
                    raise ImageProcessingError(
                        "Для обработки PDF требуется библиотека pdf2image. "
                        "Установите: pip install pdf2image"
                    )
                except Exception as e:
                    raise ImageProcessingError(f"Ошибка конвертации PDF: {str(e)}")

            else:
                raise ImageProcessingError(
                    f"Неподдерживаемый формат файла: {file_ext}"
                )

        except Exception as e:
            if isinstance(e, (ImageProcessingError, APIError)):
                raise
            raise ImageProcessingError(f"Ошибка подготовки изображения: {str(e)}")

    def generate(
            self,
            prompt: str,
            model_name: Optional[str] = None,
            **kwargs
    ) -> ModelOutput:
        """
        Генерация текста с использованием текстовой модели

        Args:
            prompt: текстовый промпт
            model_name: имя модели (по умолчанию первая текстовая)
            **kwargs: дополнительные параметры (temperature, max_tokens и т.д.)

        Returns:
            ModelOutput с результатами
        """
        try:
            # Определение модели
            if not model_name:
                model_name = ModelFactory.get_default_model(model_type=ModelType.TEXT)

            # Получение экземпляра модели
            model_instance = self._get_model_instance(model_name)

            # Проверка что модель поддерживает текст
            if not model_instance.is_text_model:
                raise ValueError(
                    f"Модель {model_name} не поддерживает текстовую генерацию. "
                    f"Тип модели: {model_instance.model_type.value}"
                )

            # Подготовка входных данных
            input_data = ModelInput(text=prompt)

            # Подготовка запроса
            request_payload = model_instance.prepare_request(input_data, **kwargs)

            logger.info(
                f"Отправка запроса к Ollama: model={model_name}, "
                f"prompt='{prompt[:50]}...'"
            )

            # Отправка запроса
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=request_payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            elapsed_time = time.time() - start_time

            # Парсинг ответа
            result = model_instance.parse_response(response.json())
            result.processing_time = elapsed_time

            return result

        except requests.exceptions.Timeout:
            return ModelOutput(
                error=f"Таймаут при обращении к Ollama ({self.timeout} сек)",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )
        except requests.exceptions.ConnectionError:
            return ModelOutput(
                error=f"Невозможно подключиться к Ollama: {self.base_url}",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )
        except Exception as e:
            return ModelOutput(
                error=f"Ошибка: {str(e)}",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )

    def analyze_image(
            self,
            file_data: bytes,
            filename: str,
            prompt: Optional[str] = None,
            model_name: Optional[str] = None,
            **kwargs
    ) -> ModelOutput:
        """
        Анализ изображения с использованием визуальной или OCR модели

        Args:
            file_data: байты файла
            filename: имя файла
            prompt: промпт для модели (опционально)
            model_name: имя модели (по умолчанию glm-ocr для OCR)
            **kwargs: дополнительные параметры

        Returns:
            ModelOutput с результатами
        """
        try:
            # Определение модели
            if not model_name:
                # По умолчанию используем первую доступную модель для анализа изображений
                try:
                    model_name = ModelFactory.get_default_model(model_type=ModelType.OCR)
                except:
                    # Если нет OCR модели, пробуем VISION
                    model_name = ModelFactory.get_default_model(model_type=ModelType.VISION)

            # Получение экземпляра модели
            model_instance = self._get_model_instance(model_name)

            # Проверка что модель поддерживает изображения
            if not model_instance.is_vision_model:
                raise ValueError(
                    f"Модель {model_name} не поддерживает анализ изображений. "
                    f"Тип модели: {model_instance.model_type.value}"
                )

            # Подготовка изображения
            image_base64 = self._prepare_image_base64(file_data, filename)

            # Подготовка входных данных
            input_data = ModelInput(
                text=prompt or model_instance.default_prompt,
                image_base64=image_base64,
                file_bytes=file_data,
                file_name=filename
            )

            # Подготовка запроса
            request_payload = model_instance.prepare_request(input_data, **kwargs)

            logger.info(
                f"Отправка запроса к Ollama: model={model_name}, "
                f"prompt='{prompt or model_instance.default_prompt}'"
            )

            # Отправка запроса
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=request_payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            elapsed_time = time.time() - start_time

            # Парсинг ответа
            result = model_instance.parse_response(response.json())
            result.processing_time = elapsed_time

            return result

        except requests.exceptions.Timeout:
            return ModelOutput(
                error=f"Таймаут при обращении к Ollama ({self.timeout} сек)",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )
        except requests.exceptions.ConnectionError:
            return ModelOutput(
                error=f"Невозможно подключиться к Ollama: {self.base_url}",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )
        except Exception as e:
            return ModelOutput(
                error=f"Ошибка: {str(e)}",
                text=None,
                confidence=None,
                meta=None,
                raw_response=None,
                tokens_used=None,
                processing_time=None
            )

    def __del__(self):
        """Закрытие сессии при уничтожении объекта"""
        if hasattr(self, 'session'):
            self.session.close()