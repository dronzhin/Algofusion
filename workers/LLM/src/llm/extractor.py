# workers/LLM/src/llm/extractor.py
"""
Экстрактор структурированных данных на базе Ollama.
"""

from typing import Optional, Dict, Any
import re
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.utils.logger import setup_logger
from workers.LLM.src.llm.base import ExtractorEngine
from workers.LLM.prompts import load_extractor_prompt
from workers.LLM.schemas import get_schema_for_type

logger = setup_logger("workers.llm.llm.extractor")


class OllamaExtractor(ExtractorEngine):
    """Экстрактор данных на базе Ollama API."""

    name = "ollama_extractor"

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "mistral:7b")
        self.timeout = config.get("ollama_timeout", 120)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 4096)
        self.json_mode = config.get("json_mode", True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _call_ollama(self, prompt: str) -> str:
        """Вызов Ollama API с retry-логикой."""
        url = f"{self.endpoint}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }

        if self.json_mode:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")

    def extract(
        self,
        text: str,
        schema: Optional[Dict[str, Any]],
        doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """Извлечение структурированных данных."""
        # Формируем промпт
        schema_obj = get_schema_for_type(doc_type)
        hints = schema_obj.get_prompt_hints() if schema_obj else ""

        prompt = load_extractor_prompt(
            text=text[:6000],  # Ограничиваем контекст
            schema=schema or {},
            doc_type=doc_type,
            prompt_hints=hints
        )

        try:
            # Запрос к Ollama
            response = self._call_ollama(prompt)

            # Парсим результат
            extracted = self._parse_response(response, schema)

            if extracted:
                # Добавляем метаданные
                extracted["_meta"] = {
                    "document_type": doc_type,
                    "model": self.model,
                }

            return extracted

        except Exception as e:
            logger.error(f"❌ Ошибка экстракции: {e}")
            return None

    def _parse_response(
        self,
        response: str,
        schema: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Парсит и валидирует ответ для экстракции."""
        try:
            # Извлекаем JSON из ответа
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.error("❌ JSON не найден в ответе")
                return None

            data = json.loads(json_match.group())

            # Базовая валидация (если есть схема)
            if schema and isinstance(data, dict):
                required = schema.get("required", [])
                for field in required:
                    if field not in data and not field.startswith("_"):
                        logger.warning(f"⚠️ Отсутствует поле: {field}")

            return data if isinstance(data, dict) else None

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            return None