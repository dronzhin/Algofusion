# services/ocr_client.py
"""
Клиент для работы с сервером распознавания текста (порт 8000)
Интегрируется с существующим error_handler.py через исключения
"""

import requests
from typing import Dict, Any
from utils.errors import OCRServerError


class OCRClient:
    """
    Клиент для сервера распознавания текста

    Эндпоинты:
      - GET  /models — список моделей
      - POST /ocr    — распознавание текста
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Инициализация клиента

        Args:
            base_url: URL сервера распознавания (по умолчанию порт 8000)
        """
        self.base_url = base_url.rstrip('/')
        # Большой таймаут для многостраничных PDF
        self.timeout = 300

    def health_check(self) -> bool:
        """Проверка доступности сервера"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def get_available_models(self) -> Dict[str, Any]:
        """
        Получение списка доступных моделей

        Возвращает:
            {
                "available_models": ["glm-ocr", "deepseek-ocr", ...],
                "loaded_models": ["glm-ocr"],
                "cuda_available": true,
                "gpu_name": "NVIDIA RTX 4090"
            }
        """
        try:
            response = requests.get(f"{self.base_url}/models", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # При ошибке возвращаем минимальный набор для работы интерфейса
            return {
                "available_models": ["glm-ocr", "deepseek-ocr", "deepseek-ocr2", "paddleocr-vl-1.5"],
                "loaded_models": [],
                "cuda_available": False,
                "gpu_name": None,
                "error": str(e)
            }

    def recognize_text(
            self,
            file_data: bytes,
            filename: str,
            model_name: str = "glm-ocr",
            prompt: str = "Extract all text",
            return_confidence: bool = True
    ) -> Dict[str, Any]:
        """
        Распознавание текста с изображения или PDF

        Args:
            file_data: байты файла (изображение или PDF)
            filename: имя файла с расширением
            model_name: имя модели ('glm-ocr', 'deepseek-ocr', 'deepseek-ocr2', 'paddleocr-vl-1.5')
            prompt: инструкция для модели (на английском)
            return_confidence: возвращать ли метрику уверенности

        Возвращает:
            Результат распознавания в формате сервера:
            {
                "model": "glm-ocr",
                "prompt": "...",
                "file_type": "image|pdf",
                "text": "распознанный текст",          # для изображений
                "pages": [...],                        # для PDF
                "confidence": 0.87,                    # если return_confidence=True
                "status": "success",
                "timing": {...},
                "request_id": "req_12345"
            }

        Выбрасывает:
            OCRServerError: при ошибках распознавания
        """
        # Валидация расширения файла
        valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.pdf')
        if not filename.lower().endswith(valid_extensions):
            raise OCRServerError(
                f"Неподдерживаемый формат файла '{filename}'. "
                f"Поддерживаются: {', '.join(valid_extensions)}",
                endpoint="/ocr",
                model_name=model_name
            )

        try:
            files = {
                "image": (filename, file_data, "application/octet-stream")
            }
            data = {
                "model_name": model_name,
                "prompt": prompt,
                "return_confidence": str(return_confidence).lower()
            }

            response = requests.post(
                f"{self.base_url}/ocr",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()

            # Проверка статуса в ответе сервера
            if result.get("status") != "success":
                detail = result.get("detail", "Неизвестная ошибка сервера")
                raise OCRServerError(
                    f"Сервер вернул ошибку: {detail}",
                    status_code=500,
                    endpoint="/ocr",
                    model_name=model_name,
                    response_data=result
                )

            return result

        except requests.exceptions.Timeout:
            raise OCRServerError(
                f"Таймаут распознавания ({self.timeout} сек). "
                f"Попробуйте уменьшить размер файла или выбрать более лёгкую модель (например, glm-ocr).",
                status_code=408,
                endpoint="/ocr",
                model_name=model_name
            )
        except requests.exceptions.ConnectionError:
            raise OCRServerError(
                f"Не удалось подключиться к серверу распознавания ({self.base_url}). "
                f"Убедитесь, что сервер запущен: 'python app.py' в директории Algofusion/OCR",
                status_code=503,
                endpoint="/ocr",
                model_name=model_name
            )
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except:
                error_detail = e.response.text

            raise OCRServerError(
                f"Ошибка сервера: {error_detail}",
                status_code=e.response.status_code,
                endpoint="/ocr",
                model_name=model_name,
                response_data=e.response.json() if e.response.content else None
            )
        except Exception as e:
            raise OCRServerError(
                f"Неожиданная ошибка: {str(e)}",
                endpoint="/ocr",
                model_name=model_name
            ) from e