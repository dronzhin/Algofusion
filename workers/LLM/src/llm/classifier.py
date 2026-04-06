# workers/LLM/src/llm/classifier.py
"""
Классификатор документов на базе Ollama.
"""

from typing import Tuple, Optional
import re
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.utils.logger import setup_logger
from workers.LLM.src.llm.base import ClassifierEngine
from workers.LLM.prompts import load_classifier_prompt

logger = setup_logger("workers.llm.llm.classifier")


class OllamaClassifier(ClassifierEngine):
    """Классификатор на базе Ollama API."""

    name = "ollama_classifier"

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "mistral:7b")
        self.timeout = config.get("ollama_timeout", 120)
        self.json_mode = config.get("json_mode", True)
        self.allowed_types = config.get("allowed_doc_types", ["unknown"])

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
                "temperature": 0.0,  # Детерминированный вывод для классификации
                "num_predict": 512,
            }
        }

        if self.json_mode:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")

    def classify(self, text: str) -> Tuple[str, float]:
        """Классификация текста документа."""
        # Ограничиваем контекст
        truncated = text[:4000]

        # Формируем промпт
        prompt = load_classifier_prompt(
            text=truncated,
            allowed_types=self.allowed_types
        )

        try:
            # Запрос к Ollama
            response = self._call_ollama(prompt)

            # Парсим результат
            result = self._parse_response(response)
            doc_type = result["type"]
            confidence = result["confidence"]

            # Валидация типа
            if doc_type not in self.allowed_types:
                logger.warning(f"⚠️ Неизвестный тип: {doc_type}, fallback на unknown")
                return "unknown", 0.0

            logger.debug(f"✅ Классификация: {doc_type} ({confidence:.2f})")
            return doc_type, confidence

        except Exception as e:
            logger.error(f"❌ Ошибка классификации: {e}")
            return "unknown", 0.0

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Парсит ответ Ollama для классификации."""
        default = {"type": "unknown", "confidence": 0.0}

        try:
            # Пытаемся найти JSON в ответе
            json_match = re.search(r'\{[^{}]*"type"[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                doc_type = data.get("type", "").lower()
                confidence = float(data.get("confidence", 0.0))
                return {
                    "type": doc_type,
                    "confidence": min(max(confidence, 0.0), 1.0)
                }

            # Fallback: парсинг простого текста
            for doc_type in self.allowed_types:
                if doc_type.lower() in response.lower():
                    return {"type": doc_type, "confidence": 0.7}

            return default

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            return default