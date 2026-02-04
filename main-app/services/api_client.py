# services/api_client.py
import requests
from typing import Dict, Any
from utils import APIError


class APIClient:
    """
    Клиент для взаимодействия с FastAPI сервером
    Инкапсулирует всю логику API запросов
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def convert_to_binary(self, file_data: bytes, filename: str, threshold: int) -> Dict[str, Any]:
        """Конвертация файла в бинарное изображение"""
        try:
            files = {
                "file": (filename, file_data, "application/octet-stream"),
                "threshold": (None, str(threshold)),
                "output_format": (None, "base64")
            }

            response = requests.post(
                f"{self.base_url}/convert",
                files=files,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise APIError(f"Ошибка при конвертации в бинарное изображение: {e}") from e

    def rotate_image(self, image_data: bytes, filename: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Выравнивание изображения"""
        try:
            files = {"file": (filename, image_data, "image/png")}

            response = requests.post(
                f"{self.base_url}/rotate",
                files=files,
                data=params,
                timeout=60
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise APIError(f"Ошибка при выравнивании изображения: {e}") from e