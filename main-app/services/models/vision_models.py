# services/models/vision_models.py
"""
Реализация визуальных и OCR моделей для Ollama
"""

from typing import Dict, Any, List
from . import ModelBase, ModelType, InputType, ModelOutput, ModelInput


class GenericVisionModel(ModelBase):
    """Базовая реализация для визуальных моделей"""

    def prepare_request(
            self,
            input_data: ModelInput,
            **kwargs
    ) -> Dict[str, Any]:
        """Подготовка запроса для визуальных моделей"""
        self.validate_input(input_data)

        temperature = kwargs.get("temperature", self.default_temperature)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)

        messages = []

        # Системный промпт (если поддерживается)
        if self.supports_system_prompt and kwargs.get("system_prompt"):
            messages.append({
                "role": "system",
                "content": kwargs["system_prompt"]
            })

        # Пользовательское сообщение с изображением
        user_message = {
            "role": "user",
            "content": input_data.text or self.default_prompt
        }

        # Добавляем изображение если есть
        if input_data.image_base64:
            user_message["images"] = [input_data.image_base64]

        messages.append(user_message)

        return {
            "model": self.model_name,
            "messages": messages,
            "stream": kwargs.get("stream", False),
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

    def parse_response(self, response_json: Dict[str, Any]) -> ModelOutput:
        """Парсинг ответа визуальных моделей"""
        try:
            text = response_json.get("message", {}).get("content", "").strip()
            tokens = response_json.get("eval_count", 0)

            return ModelOutput(
                text=text,
                tokens_used=tokens,
                raw_response=response_json
            )
        except Exception as e:
            return ModelOutput(
                error=f"Ошибка парсинга ответа: {str(e)}",
                text=None,
                confidence=None,
                meta=None,
                raw_response=response_json,
                tokens_used=None,
                processing_time=None
            )


# === Конкретные реализации (наследуются от базовой реализации) ===

class GlmOcrModel(GenericVisionModel):
    """GLM-OCR - специализированная модель для распознавания текста"""

    model_name: str = "glm-ocr:latest"
    display_name: str = "GLM-OCR"
    model_type: ModelType = ModelType.OCR
    input_type: InputType = InputType.TEXT_AND_IMAGE

    supports_streaming: bool = False
    supports_confidence: bool = False
    supports_multilingual: bool = True
    supports_system_prompt: bool = False

    default_prompt: str = "Extract all text from this image. Preserve structure and layout."
    default_temperature: float = 0.0
    default_max_tokens: int = 2048

    description: str = "Специализированная модель для распознавания текста с изображений"
    use_cases: List[str] = ["OCR", "Распознавание текста", "Извлечение данных с документов"]
    languages: List[str] = ["en", "ru", "zh"]


class LlavaVisionModel(GenericVisionModel):
    """LLaVA - мультимодальная модель для анализа изображений"""

    model_name: str = "llava:latest"
    display_name: str = "LLaVA"
    model_type: ModelType = ModelType.VISION
    input_type: InputType = InputType.TEXT_AND_IMAGE

    supports_streaming: bool = True
    supports_confidence: bool = False
    supports_multilingual: bool = True
    supports_system_prompt: bool = True

    default_prompt: str = "You are a helpful assistant that can analyze images. Describe what you see."
    default_temperature: float = 0.7
    default_max_tokens: int = 1024

    description: str = "Мультимодальная модель для анализа и описания изображений"
    use_cases: List[str] = ["Описание изображений", "Анализ визуального контента", "Ответы на вопросы по изображению"]
    languages: List[str] = ["en", "ru"]


class MoondreamVisionModel(GenericVisionModel):
    """Moondream - компактная визуальная модель"""

    model_name: str = "moondream:latest"
    display_name: str = "Moondream"
    model_type: ModelType = ModelType.VISION
    input_type: InputType = InputType.TEXT_AND_IMAGE

    supports_streaming: bool = False
    supports_confidence: bool = False
    supports_multilingual: bool = True
    supports_system_prompt: bool = True  # Добавлено отсутствующее поле

    default_prompt: str = "Describe this image."
    default_temperature: float = 0.7
    default_max_tokens: int = 512

    description: str = "Компактная и быстрая модель для анализа изображений"
    use_cases: List[str] = ["Быстрое описание изображений", "Простой анализ"]
    languages: List[str] = ["en"]