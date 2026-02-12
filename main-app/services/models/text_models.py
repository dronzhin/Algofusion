# services/models/text_models.py
"""
Реализация текстовых моделей для Ollama
"""

from typing import Dict, Any
from . import ModelBase, ModelType, InputType, ModelOutput, ModelInput
import logging

logger = logging.getLogger(__name__)

class GenericTextModel(ModelBase):
    """Универсальная текстовая модель (базовая реализация)"""

    def prepare_request(
        self,
        input_data: ModelInput,
        **kwargs: dict
    ) -> Dict[str, Any]:
        """Подготовка запроса для текстовых моделей"""
        self.validate_input(input_data)

        if not input_data.text:
            raise ValueError("Текстовый ввод обязателен для GenericTextModel.")

        temperature = kwargs.get("temperature", self.default_temperature)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
        system_prompt = kwargs.get("system_prompt", self.default_prompt)

        messages = []

        if self.supports_system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": input_data.text})

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
        """Парсинг ответа текстовых моделей"""
        try:
            text = response_json.get("message", {}).get("content", "").strip()
            tokens = response_json.get("eval_count", 0)

            return ModelOutput(
                text=text,
                tokens_used=tokens,
                raw_response=response_json,
                confidence=None,
                metadata=None,
                processing_time=None
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга ответа: {str(e)}")
            return ModelOutput(
                error=f"Ошибка парсинга ответа: {str(e)}",
                text=None,
                confidence=None,
                metadata=None,
                raw_response=response_json,
                tokens_used=None,
                processing_time=None
            )

class Llama3TextModel(GenericTextModel):
    """Llama 3 - мощная текстовая модель"""
    model_name: str = "llama3:latest"
    display_name: str = "Llama 3"
    model_type: ModelType = ModelType.TEXT
    input_type: InputType = InputType.TEXT_ONLY
    # ... остальные поля ...

class CodeLlamaModel(GenericTextModel):
    """CodeLlama - специализированная модель для кода"""
    # ... поля класса ...

    def prepare_request(
        self,
        input_data: ModelInput,
        **kwargs: dict
    ) -> Dict[str, Any]:
        """Подготовка запроса для CodeLlama с упором на код"""
        if not input_data.text:
            raise ValueError("Текстовый ввод обязателен для CodeLlamaModel.")

        request = super().prepare_request(input_data, **kwargs)

        if "options" in request:
            request["options"]["stop"] = ["```", "def ", "class ", "if ", "for ", "while ", "{", "}"]

        return request
