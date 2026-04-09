#!/usr/bin/env python3
# workers/LLM/src/llm/classifier.py
"""
Классификатор документов на базе Ollama с strict JSON mode.
Использует DocumentType enum из shared.models.file.enums.
"""

from typing import Tuple, Optional, Dict, Any, List
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.utils.logger import setup_logger
from shared.models.file.enums import DocumentType
from workers.LLM.src.llm.base import ClassifierEngine
from workers.LLM.prompts import load_classifier_prompt

logger = setup_logger("workers.llm.classifier")


class OllamaClassifier(ClassifierEngine):
    """Классификатор на базе Ollama API с strict JSON output."""

    name = "ollama_classifier"

    # 🔹 Строгая схема ответа для классификации
    CLASSIFICATION_SCHEMA = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": []  # Заполняется динамически из allowed_types
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0
            }
        },
        "required": ["type", "confidence"],
        "additionalProperties": False  # 🔹 Запрещаем лишние поля!
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("ollama_endpoint", "http://ollama:11434")
        self.model = config.get("ollama_model", "qwen2.5:1.5b")
        self.timeout = config.get("ollama_timeout", 120)

        # 🔹 Получаем allowed_types из config или из DocumentType enum
        raw_types = config.get("allowed_doc_types", [])
        self.allowed_types: List[str] = []
        for t in raw_types:
            # Преобразуем в канонический вид через enum
            parsed = DocumentType.safe_parse(t)
            if parsed:
                self.allowed_types.append(parsed.value)
            elif t in [dt.value for dt in DocumentType]:
                self.allowed_types.append(t)

        if not self.allowed_types:
            self.allowed_types = [dt.value for dt in DocumentType]

        # 🔹 Обновляем enum в схеме динамически
        self._schema = self.CLASSIFICATION_SCHEMA.copy()
        self._schema["properties"]["type"]["enum"] = self.allowed_types

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, json.JSONDecodeError)),
        reraise=True
    )
    def _call_ollama(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """Вызов Ollama API с strict JSON mode."""
        url = f"{self.endpoint}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,  # 🔹 Детерминированный вывод
                "num_predict": 256,
            }
        }

        # 🔹 STRICT JSON MODE: передаём схему напрямую в Ollama
        if schema:
            payload["format"] = schema
        else:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            raw_response = result.get("response", "")
            return self._extract_json_from_response(raw_response)

    def _extract_json_from_response(self, text: str) -> str:
        """Извлекает валидный JSON из ответа модели."""
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            candidate = text[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return text.strip()

    def classify(self, text: str) -> Tuple[str, float]:
        """Классификация текста документа с strict JSON."""
        truncated = text[:4000]
        prompt = load_classifier_prompt(text=truncated, allowed_types=self.allowed_types)

        try:
            response = self._call_ollama(prompt, schema=self._schema)
            result = json.loads(response)
            doc_type = result.get("type", "unknown")
            confidence = float(result.get("confidence", 0.0))
            confidence = min(max(confidence, 0.0), 1.0)

            if doc_type not in self.allowed_types:
                logger.warning(f"⚠️ Неизвестный тип: {doc_type}, fallback на unknown")
                return "unknown", 0.0

            logger.debug(f"✅ Классификация: {doc_type} ({confidence:.2f})")
            return doc_type, confidence

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}, raw: {response[:200]}")
            return "unknown", 0.0
        except Exception as e:
            logger.error(f"❌ Ошибка классификации: {e}")
            return "unknown", 0.0