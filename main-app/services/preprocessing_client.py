# services/preprocessing_client.py
"""
Клиент для сервера предобработки изображений (порт 8001)
Отделён от клиента распознавания для избежания путаницы
"""

import requests
from typing import Dict, Any
from utils.errors import PreprocessingServerError


class PreprocessingClient:
    """
    Клиент для сервера предобработки изображений

    Эндпоинты:
      - POST /convert — бинаризация
      - POST /rotate  — выравнивание
    """

    def __init__(self, base_url: str = "http://localhost:8001"):
        """
        Инициализация клиента

        Args:
            base_url: URL сервера предобработки (по умолчанию порт 8001)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = 30

    def health_check(self) -> bool:
        """Проверка доступности сервера"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def convert_to_binary(
            self,
            file_data: bytes,
            filename: str,
            threshold: int = 128
    ) -> Dict[str, Any]:
        """
        Конвертация в бинарное изображение

        Args:
            file_data: байты исходного файла
            filename: имя файла
            threshold: порог бинаризации (0-255)

        Возвращает:
            Результат обработки в формате сервера

        Выбрасывает:
            PreprocessingServerError: при ошибках взаимодействия с сервером
        """
        try:
            files = {"file": (filename, file_data, "application/octet-stream")}
            data = {"threshold": str(threshold)}

            response = requests.post(
                f"{self.base_url}/convert",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise PreprocessingServerError(
                f"Таймаут бинаризации ({self.timeout} сек)",
                status_code=408,
                operation="convert"
            )
        except requests.exceptions.ConnectionError:
            raise PreprocessingServerError(
                f"Не удалось подключиться к серверу предобработки ({self.base_url})",
                status_code=503,
                operation="convert"
            )
        except Exception as e:
            raise PreprocessingServerError(
                f"Ошибка бинаризации: {str(e)}",
                operation="convert"
            ) from e

    def rotate_image(
            self,
            image_data: bytes,
            filename: str,
            params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Выравнивание изображения

        Args:
            image_data: байты изображения
            filename: имя файла
            params: параметры выравнивания

        Возвращает:
            Результат обработки в формате сервера

        Выбрасывает:
            PreprocessingServerError: при ошибках взаимодействия с сервером
        """
        try:
            files = {"file": (filename, image_data, "image/png")}

            response = requests.post(
                f"{self.base_url}/rotate",
                files=files,
                data=params,
                timeout=self.timeout * 2  # Поворот может занимать больше времени
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise PreprocessingServerError(
                f"Таймаут выравнивания ({self.timeout * 2} сек)",
                status_code=408,
                operation="rotate"
            )
        except requests.exceptions.ConnectionError:
            raise PreprocessingServerError(
                f"Не удалось подключиться к серверу предобработки ({self.base_url})",
                status_code=503,
                operation="rotate"
            )
        except Exception as e:
            raise PreprocessingServerError(
                f"Ошибка выравнивания: {str(e)}",
                operation="rotate"
            ) from e